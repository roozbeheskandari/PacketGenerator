# PacketGenerator
Several Steps to recieve success on OVS in Baseline, withLocalCuckooFilter,withGlobalCuckooFilter+AI,withLocal&GlobalCuckooFilter+AI


بخش اول: پیش‌نیازها و کامپایل و نصب OVS
ابتدا پکیج‌های ابزار ساخت را نصب کنید:


sudo apt update
sudo apt install -y build-essential libssl-dev autoconf automake libtool \
    python3-pip libnuma-dev libpcap-dev libunbound-dev iproute2 iperf3 tshark
سپس وارد دایرکتوری برنچی که اصلاح کردید (مثلاً full-global-ai-local-cuckoo یا نسخه دو لایه) بشوید و مراحل زیر را اجرا کنید:


# ۱. تولید اسکریپت‌های پیکربندی
./boot.sh

# ۲. پیکربندی OVS
./configure --prefix=/usr --localstatedir=/var --sysconfdir=/etc

# ۳. کامپایل با تمام هسته‌های CPU
make -j$(nproc)

# ۴. نصب باینری‌ها
sudo make install
(اگر در مرحله make خطایی مشاهده کردید، متن چند خط آخر ترمینال را کپی و ارسال کنید).

بخش دوم: راه‌اندازی دیتابیس و سرویس OVS
اگر سرویس پیش‌فرضی از قبل فعال است متوقف کنید و سرویس جدید را با دیتابیس تازه بالا بیاورید:


# پاکسازی و ساخت مجدد دیتابیس
sudo /usr/share/openvswitch/scripts/ovs-ctl stop || true
sudo rm -rf /etc/openvswitch/conf.db
sudo ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema

# استارت ovsdb-server و ovs-vswitchd
sudo ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \
    --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
    --pidfile --detach

sudo ovs-vsctl --no-wait init
sudo ovs-vswitchd --pidfile --detach --log-file=/var/log/openvswitch/ovs-vswitchd.log
بخش سوم: ساخت محیط تست ایزوله (Network Namespaces)
برای اینکه بدون نیاز به سخت‌افزار DPDK یا کارت شبکه فیزیکی، ترافیک بالا تست شود، از ۲ فضای نام (Namespace) و اینترفیس مجازی veth متصل به بریج Netdev (یوزراسپیس) استفاده می‌کنیم:


# ۱. ساخت بریج یوزراسپیس
sudo ovs-vsctl add-br br-test -- set bridge br-test datapath_type=netdev

# ۲. ساخت دو شبکه ایزوله (ns1 و ns2)
sudo ip netns add ns1
sudo ip netns add ns2

# ۳. ایجاد جفت پورت‌های مجازی
sudo ip link add veth1 type veth peer name ovs-veth1
sudo ip link add veth2 type veth peer name ovs-veth2

# ۴. اتصال پورت‌ها به محیط‌های شبکه
sudo ip link set veth1 netns ns1
sudo ip link set veth2 netns ns2
sudo ip link set ovs-veth1 up
sudo ip link set ovs-veth2 up

# ۵. افزودن پورت‌ها به OVS
sudo ovs-vsctl add-port br-test ovs-veth1
sudo ovs-vsctl add-port br-test ovs-veth2

# ۶. تنظیم IPها و فعال‌سازی اینترفیس‌ها
sudo ip netns exec ns1 ip addr add 10.0.0.1/24 dev veth1
sudo ip netns exec ns1 ip link set veth1 up
sudo ip netns exec ns1 ip link set lo up

sudo ip netns exec ns2 ip addr add 10.0.0.2/24 dev veth2
sudo ip netns exec ns2 ip link set veth2 up
sudo ip netns exec ns2 ip link set lo up
یک تست پینگ ساده انجام دهید:


sudo ip netns exec ns1 ping -c 3 10.0.0.2
بخش چهارم: تعریف Flowها برای تست رفتار Subtable و فیلترها
برای اینکه چند ساب‌تیبل با ماسک‌های مختلف شکل بگیرند (و عملکرد لوک‌آپ، رد شدن با کوکو فیلتر و پرش به مسیر اصلی بررسی شود):


# ایجاد رول‌های چندگانه با الگوهای مختلف (تولید چند Subtable مجزا در dpcls)
sudo ovs-ofctl del-flows br-test

# رول ۱: بر اساس پورت و IP
sudo ovs-ofctl add-flow br-test "priority=100,ip,nw_src=10.0.0.1,nw_dst=10.0.0.2,tcp,tp_dst=5001 actions=output:ovs-veth2"

# رول ۲: بر اساس پورت مبدا متفاوت
sudo ovs-ofctl add-flow br-test "priority=90,ip,nw_src=10.0.0.1,nw_dst=10.0.0.2,udp,tp_dst=5002 actions=output:ovs-veth2"

# رول پیش‌فرض
sudo ovs-ofctl add-flow br-test "priority=10 actions=NORMAL"


# نصب ابزارهای شبکه و tcpreplay
sudo apt update && sudo apt install -y tcpreplay python3-psutil

# ساخت فایل ترافیک قطعی (100,000 پکت)
python3 traffic_gen.py

#Run This before everyTest
sudo ovs-ofctl del-flows br-test
sudo ovs-ofctl add-flow br-test "priority=100,ip,nw_src=10.0.0.1,nw_dst=10.0.0.2,tp_dst=5001 actions=output:ovs-veth2"
sudo ovs-ofctl add-flow br-test "priority=95,ip,nw_src=10.0.0.1,nw_dst=10.0.0.2,udp,tp_dst=5002 actions=output:ovs-veth2"
sudo ovs-ofctl add-flow br-test "priority=90,ip,nw_src=10.0.0.0/24,udp actions=output:ovs-veth2"
sudo ovs-ofctl add-flow br-test "priority=85,ip,nw_dst=10.0.0.2,udp,tp_dst=6000 actions=output:ovs-veth2"
sudo ovs-ofctl add-flow br-test "priority=80,ip,nw_src=10.0.0.1,tp_dst=7000 actions=output:ovs-veth2"
sudo ovs-ofctl add-flow br-test "priority=100,in_port=ovs-veth2 actions=output:ovs-veth1"
sudo ovs-ofctl add-flow br-test "priority=10 actions=NORMAL"

################################

   make -j$(nproc)
   sudo make install
   sudo systemctl restart openvswitch-switch

   sudo python3 run_benchmark.py --scenario BASE
   sudo python3 run_benchmark.py --scenario LOCAL
   sudo python3 run_benchmark.py --scenario GLOBAL_AI
   sudo python3 run_benchmark.py --scenario FULL_TIER

