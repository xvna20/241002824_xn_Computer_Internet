一、运行环境
1.Python 3.13.12
2.用到模块：socket、time、sys、random、os、threading、pandas，其中pandas为第三方库，需安装
3.适用系统：Windows/Linux
二、文件说明（task2）
   udpserver.py            服务端程序
   udpclient.py            客户端程序
   run_log_client.txt      客户端运行日志文件
   run_log_server.txt      服务端运行日志文件
   readme.txt              本说明文档
三、启动步骤
1.启动服务端
   python3 /mnt/hgfs/vm_share/task2/udpserver.py
   服务端默认监听0.0.0.0:9999，启动后持续接收客户端消息。
   服务端会以10%的概率模拟丢包。
2.打开另一终端启动客户端
   命令格式：
   python udpclient.py IP PORT
   参数说明：
   IP：服务端地址
   PORT：服务端端口
   测试示例：
   python udpclient.py 192.168.78.128 9999
3.程序运行结果说明
   （1）run_log.txt：全程记录客户端、服务端收发日志
   （2）客户端控制台实时打印每个数据包的发送、确认与重传信息
   （3）程序结束后客户端输出汇总统计：丢包率、最大/最小/平均RTT、RTT标准差
四、协议首部定义与报文格式
1.首部字段总表（所有报文通用，6个key=value字段，竖线|分隔）
   字段名称     含义          
   StudentID    学号后4位^0x5A3C
   MsgType      报文类型
   SeqNum       序列号
   AckNum       确认号
   DataLen      后续数据字节长度
   Flags        标志位
2.MsgType取值
   MsgType  名称   说明
   1        CONN   连接建立（配合Flags区分SYN/SYN+ACK/ACK）
   2        DATA   数据传输
   3        ACK    确认应答
3.Flags取值
   Flags     含义
   SYN       请求建立连接
   SYN+ACK   同意连接
   ACK       确认
4.报文格式示例
   ·连接建立（三次握手）：
   （1）客户端-->服务端：
      StudentID=20788|MsgType=1|SeqNum=0|AckNum=0|DataLen=0|Flags=SYN
   （2）服务端-->客户端：
      StudentID=20788|MsgType=1|SeqNum=0|AckNum=1|DataLen=0|Flags=SYN+ACK
   （3）客户端-->服务端：
         StudentID=20788|MsgType=1|SeqNum=0|AckNum=1|DataLen=0|Flags=ACK
   ·数据传输（GBN协议+累积确认）：
   （1）客户端-->服务端：
         StudentID=20788|MsgType=2|SeqNum=1|AckNum=0|DataLen=40|Flags=0|D*40
         序列号从1开始递增，数据长度40~80字节随机
   （2）服务端-->客户端：
         StudentID=20788|MsgType=3|SeqNum=0|AckNum=1|DataLen=0|Flags=ACK
         AckNum表示所有≤该序列号的包已收到
5.超时重传
   （1）客户端超时时间：300ms
   （2）超时后回退到base位置，重传窗口内所有未确认的包
五、滑动窗口与可靠传输机制
1.窗口大小：5
2.GBN（Go-Back-N）协议：
   （1）窗口内连续发送，等待ACK
   （2）收到ACK后窗口向前滑动
   （3）超时则回退重传窗口内所有包
3.累积确认：
   （1）服务端按序接收，ACK=连续收到的最大序列号
   （2）乱序到达则发送重复ACK，触发客户端重传
六、学号验证机制
1.固定XOR掩码：0x5A3C
2.客户端发送：syn_val=学号后4位^0x5A3C
3.服务端解密：real_id=syn_val^0x5A3C
4.校验范围：0~9999，通过则同意连接
5.客户端学号后4位配置：udpclient.py中STUDENT_LAST4变量(2824)
七、配置选项
   udpserver.py：
         SERVER_PORT      服务端端口（设定9999）
         PACKET_LOSS_RATE   模拟丢包率（0.1即10%）
         STUDENT_XOR_CODE   学号校验XOR码（固定0x5A3C）
         BUFFER_SIZE      接收缓冲区大小
   udpclient.py：
         STUDENT_LAST4    学号后4位（2824）
         SERVER_PORT      服务端端口（设定9999）
         TIMEOUT_SEC      超时时间（300ms）
         WINDOW_SIZE      滑动窗口大小（5）
         MIN_PAYLOAD      单包最小数据长度（40字节）
         MAX_PAYLOAD      单包最大数据长度（80字节）
         TOTAL_PACKETS    总发送包数
八、统计输出
   客户端运行结束后输出汇总信息：
   1.丢包率=(总发送次数-30)/总发送次数*100%
   2.最大RTT、最小RTT、平均RTT、RTT标准差
