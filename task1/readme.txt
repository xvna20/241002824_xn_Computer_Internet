一、运行环境
1. Python 3.13.12
2. 用到模块：socket、struct、random、sys、datetime，全部为Python标准库，无需额外安装第三方包
3. 适用系统：Windows/Linux

二、文件说明（task1）
    reversetcpserver.py    服务端程序
    reversetcpclient.py    客户端程序
    test.txt               原始测试文件（ASCII文本）
    result_rev.txt         运行后生成的结果文件（每块字符串被反转后拼接）
    run_log.txt            运行日志文件（记录服务端与客户端交互过程）
    run_log.lock           锁文件（运行时生成，用于跨进程日志同步，程序退出自动删除）
    readme.txt             本说明文档

三、启动步骤
1. 启动服务端
打开linux终端，进入代码所在目录（需要将代码文件放置虚拟机与本机的共享文件夹vm_share中），执行：
python3 /mnt/hgfs/vm_share/task1/reversetcpserver.py 
服务端默认监听192.168.78.128:9999，启动后阻塞等待客户端接入。
2. 打开本机终端启动客户端
命令格式：
python reversetcpclient.py IP PORT LMIN LMAX SEED
参数说明：
IP：服务端地址；
PORT：端口；
LMIN：单块最小字节；
LMAX：单块最大字节；
SEED：随机种子(固定种子=分块长度固定)
测试示例：
python reversetcpclient.py 192.168.78.128 9999 5 10 2
3.程序运行产物说明
（1）run_log.txt：全程记录客户端、服务端收发日志
（2）客户端控制台（主机终端）实时打印每一块的反转内容
（3）result_rev.txt：全部数据传输完成后自动生成，保存全文反转结果

四、分块规则
（1）读取test.txt全部ASCII内容
（2）从文件头开始，每块长度在[Lmin, Lmax]区间内随机取值
（3）最后一块为剩余字节（可能小于Lmin）
（4）总块数N由分块结果决定，随Lmin/Lmax而变

五、通信协议（报文格式）
（1）初始化报文（客户端→服务端）
    Type(2B) | N(4B)
    字段: Type=1, N=总块数
（2）同意报文（服务端→客户端）
    Type(2B)
    字段:Type=2
（3）反转请求报文（客户端→服务端）
    Type(2B) | Length(2B) | Data(Length B)
    字段: Type=3, Length=本块长度, Data=原始字符串的ASCII字节
（4）应答报文（服务端→客户端）
    Type(2B) | Length(2B) | ReverseData(Length B)
    字段: Type=4, Length=反转后数据长度, ReverseData=反转后的ASCII字节

六、服务端多客户端支持
（1）服务端使用threading为每个连接创建独立子线程
（2）可同时服务多个客户端，互不干扰
（3）主线程持续accept()等待新连接

七、注意事项
（1）test.txt必须是纯ASCII编码文本
（2）服务端端口9999若被占用，可修改代码中的端口号
（3）先启动服务端，再启动客户端
（4）结果文件result_rev.txt每次运行会被覆盖

