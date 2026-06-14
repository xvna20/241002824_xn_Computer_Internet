import socket
import time
import sys
import random
import os
import pandas as pd
import threading
# 获取当前脚本所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 客户端日志文件路径
LOG_FILE = os.path.join(BASE_DIR, "run_log_client.txt")
# 日志写入线程锁，保证多线程安全写入
_log_lock = threading.Lock()

def write_log(info):
    t = time.strftime("%Y-%m-%d %H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}"
    with _log_lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{t}] Client: {info}\n")

STUDENT_LAST4=2824
SERVER_PORT=9999
TIMEOUT_SEC=0.3          #超时时间，超时后执行GBN回退重传
WINDOW_SIZE=5            #GBN滑动窗口大小
STUDENT_XOR_CODE=0x5A3C  #异或校验码，用于验证学号
MIN_PAYLOAD=40
MAX_PAYLOAD=80
TOTAL_PACKETS=30         #需要发送的数据包总数

# 线程锁，用于保护共享状态变量
_lock = threading.Lock()
# 条件变量，用于发送线程等待ACK
_cond = threading.Condition(_lock)
# 窗口基序号（base），表示已确认的最大序号+1
_base = 1
# 下一个待发送序号（next_seqnum）
_next_seq = 1
# 接收线程退出标志
_done = False

def make_packet(student_id, msg_type, seq_num, ack_num, data_len, flags, data=""):
    # 构造UDP数据包
    header = f"StudentID={student_id}|MsgType={msg_type}|SeqNum={seq_num}|AckNum={ack_num}|DataLen={data_len}|Flags={flags}"
    if data:
        return f"{header}|{data}"
    return header


def parse_packet(msg_str):
    # 解析接收到的数据包
    parts = msg_str.split("|", 6)
    fields = {}
    for i in range(min(6, len(parts))):
        if "=" in parts[i]:
            k, v = parts[i].split("=", 1)
            fields[k] = v
    data_str = parts[6] if len(parts) > 6 else ""
    return fields, data_str


def packet_summary(pkt):
    # 生成数据包的摘要显示（用于日志和打印）
    parts = pkt.split("|", 6)
    display_parts = " | ".join(parts[:6])
    if len(parts) > 6 and len(parts[6]) > 10:
        return f"{display_parts} | D*{len(parts[6])}"
    if len(parts) > 6:
        return f"{display_parts} | {parts[6]}"
    return display_parts


def get_timestamp():
    # 获取当前时间戳（精确到毫秒）
    time_str = time.strftime("%H:%M:%S.")
    ms = int(time.time() * 1000) % 1000
    return time_str + f"{ms:03d}"

def connect_server(sock, server_ip, server_port):
    # 与服务端建立三次握手连接
    syn_val = STUDENT_LAST4 ^ STUDENT_XOR_CODE #计算学号异或值用于标识
    pkt = make_packet(syn_val, 1, 0, 0, 0, "SYN") #构造SYN包
    
    print(f"[{get_timestamp()}] 第1步 - 发送 SYN 连接请求")
    print(f"  → 发送报文: {packet_summary(pkt)}")
    write_log(f"发送 SYN | {packet_summary(pkt)}")
    sock.sendto(pkt.encode(), (server_ip, server_port))
    
    try:
        # 等待接收服务端的SYN+ACK响应
        resp, _ = sock.recvfrom(1024)
        resp_str = resp.decode("utf-8", errors="ignore")
        fields, _ = parse_packet(resp_str)
        
        # 验证是否为SYN+ACK包
        if fields.get("MsgType") == "1" and fields.get("Flags") == "SYN+ACK":
            print(f"[{get_timestamp()}] 第2步 - 收到 SYN-ACK 响应")
            print(f"  ← 收到报文: {packet_summary(resp_str)}")
            write_log(f"收到 SYN-ACK | {packet_summary(resp_str)}")
            
            # 发送第三次握手的ACK
            pkt2 = make_packet(syn_val, 1, 1, 1, 0, "ACK")
            print(f"[{get_timestamp()}] 第3步 - 发送 ACK 确认...")
            print(f"  → 发送报文: {packet_summary(pkt2)}")
            write_log(f"发送 ACK | {packet_summary(pkt2)}")
            sock.sendto(pkt2.encode(), (server_ip, server_port))
            
            print(f"[{get_timestamp()}] 三次握手完成，连接已建立")
            write_log("三次握手完成，连接已建立")
            return True
        return False
    except socket.timeout:
        return False
    
def generate_random_data(length):
    # 生成指定长度的随机测试数据
    return "D" * length

def ack_receiver(sock, server_ip, server_port, send_times, packet_info, rtt_list):
    global _base, _done
    syn_val = STUDENT_LAST4 ^ STUDENT_XOR_CODE
    
    # 持续运行，直到_done被设为True
    while not _done:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode("utf-8", errors="ignore")
            fields, _ = parse_packet(msg)
            
            # 只处理ACK类型的消息（MsgType=3）
            if fields.get("MsgType") == "3":
                ack_seq = int(fields.get("AckNum", 0))
                
                with _lock:
                    # 如果收到的ACK比当前base大，则更新base
                    if ack_seq + 1 > _base:
                        old_base = _base
                        _base = ack_seq + 1
                        
                        # 对所有被确认的包计算RTT
                        for seq in range(old_base, _base):
                            if seq in packet_info and seq in send_times:
                                # 计算往返时间（毫秒）
                                rtt = round((time.time() - send_times[seq]) * 1000, 2)
                                rtt_list.append(rtt)
                                start, end, _ = packet_info[seq]
                                curr_time = get_timestamp()
                                print(f"[{curr_time}] 第{seq}个（第{start}~{end}字节）server端已经收到，RTT是 {rtt} ms")
                                write_log(f"收到 ACK | Seq={seq} | RTT={rtt}ms | 确认报文: {packet_summary(make_packet(syn_val, 3, 0, seq, 0, 'ACK'))}")
                        
                        # 通知发送线程有新ACK到达
                        _cond.notify()
        except:
            pass

def main():
    global _base, _next_seq, _done
    if len(sys.argv) != 3:
        print("使用方法: python udpclient.py 服务端IP 服务端端口")
        print("例如：python udpclient.py 127.0.0.1 9999")
        return

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    
    # 创建UDP socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("=" * 60)
    print("UDP 可靠传输客户端")
    print(f"目标服务端: {server_ip}:{server_port}")
    print(f"学号后4位: {STUDENT_LAST4:04d}")
    print(f"超时时间: {TIMEOUT_SEC*1000:.0f}ms")
    print(f"滑动窗口: {WINDOW_SIZE}")
    print("=" * 60)
    print()
    print("[客户端] 正在连接服务端...")
    client_socket.settimeout(5.0)
    if not connect_server(client_socket, server_ip, server_port):
        print("[客户端]  连接失败！")
        return
    client_socket.settimeout(None)
    print("[客户端]  连接成功！")
    print()

    write_log("客户端启动，开始连接服务端")

    rtt_list = []           #存储RTT值列表
    send_times = {}         #记录每个序号的发送时间
    packet_info = {}        #记录每个序号对应的字节范围信息
    # ACK接收线程职责：专门接收ACK，不做发包和重传
    t_ack = threading.Thread(target=ack_receiver, args=(client_socket, server_ip, server_port, send_times, packet_info, rtt_list), daemon=True)
    t_ack.start()

    total_send_count = 0   #总发送次数（含重传）
    byte_offset = 1         #字节偏移量，用于记录数据范围
    syn_val = STUDENT_LAST4 ^ STUDENT_XOR_CODE

    while True:
        with _lock:
            # 当base超过总包数时，发送完成
            if _base > TOTAL_PACKETS:
                break

            current_base = _base
            
            # 在窗口范围内发送数据包
            while _next_seq < current_base + WINDOW_SIZE and _next_seq <= TOTAL_PACKETS:
                # 为新序号分配数据信息
                if _next_seq not in packet_info:
                    # 随机生成数据包大小
                    data_len = random.randint(MIN_PAYLOAD, MAX_PAYLOAD)
                    start_byte = byte_offset
                    end_byte = byte_offset + data_len - 1
                    packet_info[_next_seq] = (start_byte, end_byte, data_len)
                    byte_offset += data_len
                else:
                    start_byte, end_byte, data_len = packet_info[_next_seq]
                
                # 构造数据包
                data = generate_random_data(data_len)
                packet = make_packet(syn_val, 2, _next_seq, 0, data_len, "0", data)

                # 打印并记录发送信息
                curr_time = get_timestamp()
                print(f"[{curr_time}] 第{_next_seq}个（第{start_byte}~{end_byte}字节）client端已经发送")
                print(f"  → 发送报文: {packet_summary(packet)}")
                write_log(f"发送数据包 | Seq={_next_seq} | {packet_summary(packet)}")

                # 记录发送时间并发送数据包
                send_time = time.time()
                client_socket.sendto(packet.encode(), (server_ip, server_port))
                send_times[_next_seq] = send_time
                total_send_count += 1
                _next_seq += 1
                current_base = _base

            # 检查是否发送完成
            if _base > TOTAL_PACKETS:
                break

            # 等待ACK或超时
            old_base = _base
            _cond.wait(TIMEOUT_SEC)

            # 如果base没有更新，说明超时了，执行GBN回退重传
            if _base == old_base:
                curr_time = get_timestamp()
                print(f"[{curr_time}]  超时：{TIMEOUT_SEC*1000:.0f}ms内未收到有效ACK，GBN回退重传 base={_base}, next_seq={_next_seq}")
                write_log(f"超时重传 | base={_base} | next_seq={_next_seq}")
                
                # GBN策略：从base开始重新发送所有已发包
                for seq in range(_base, _next_seq):
                    start_byte, end_byte, data_len = packet_info[seq]
                    data = generate_random_data(data_len)
                    packet = make_packet(syn_val, 2, seq, 0, data_len, "0", data)
                    write_log(f"重传 | Seq={seq} | {packet_summary(packet)}")
                    curr_time = get_timestamp()
                    print(f"[{curr_time}]  重传第{seq}个（第{start_byte}~{end_byte}字节） | {packet_summary(packet)}")
                    send_time = time.time()
                    client_socket.sendto(packet.encode(), (server_ip, server_port))
                    send_times[seq] = send_time
                    total_send_count += 1

    _done = True  # 通知ACK接收线程退出
    client_socket.close()  # 关闭socket连接

    print(f"\n[{get_timestamp()}]  所有数据包发送完成！")
    write_log("发送完成")

    print("\n" + "=" * 60)
    print("【汇总】")
    
    # 计算丢包率（基于重传次数）
    loss_rate = ((total_send_count - 30) / total_send_count) * 100
    print(f" 丢包率: {loss_rate:.1f}%")

    # 如果有RTT数据，计算统计值
    if rtt_list:
        df = pd.DataFrame(rtt_list, columns=['RTT'])
        max_rtt = df['RTT'].max()
        min_rtt = df['RTT'].min()
        mean_rtt = df['RTT'].mean()
        std_rtt = df['RTT'].std()

        print(f" 最大RTT: {max_rtt:.2f} ms")
        print(f" 最小RTT: {min_rtt:.2f} ms")
        print(f" 平均RTT: {mean_rtt:.2f} ms")
        print(f" RTT标准差: {std_rtt:.2f} ms")

    print("=" * 60)

if __name__ == "__main__":
    main()
