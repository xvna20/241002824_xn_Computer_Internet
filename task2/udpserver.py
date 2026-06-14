import socket
import random
import time
import os
import threading
import queue
# 获取当前脚本所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 服务端日志文件路径
LOG_FILE = os.path.join(BASE_DIR, "run_log_server.txt")

# 日志写入线程锁，保证多线程安全写入
_log_lock = threading.Lock()

def write_log(info):
    t = time.strftime("%Y-%m-%d %H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}"
    with _log_lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{t}] Server: {info}\n")

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
    # 生成数据包的摘要显示

    parts = pkt.split("|", 6)
    display_parts = " | ".join(parts[:6])
    if len(parts) > 6 and len(parts[6]) > 10:
        return f"{display_parts} | D*{len(parts[6])}"
    if len(parts) > 6:
        return f"{display_parts} | {parts[6]}"
    return display_parts

SERVER_IP = "0.0.0.0"       #监听地址，0.0.0.0表示接受所有网卡连接
SERVER_PORT = 9999          #监听端口
PACKET_LOSS_RATE = 0.1      #模拟丢包率（10%）
STUDENT_XOR_CODE = 0x5A3C   #异或校验码，用于验证学号
BUFFER_SIZE = 1024           #接收缓冲区大小

#存储每个客户端的消息队列
client_queues = {}
# 存储每个客户端的处理线程
client_threads = {}
# 线程锁，保护客户端队列字典
client_queues_lock = threading.Lock()

def client_handler(client_addr, q, student_id, server_socket):
    # 客户端处理线程（每个客户端一个独立线程）
    # 期望收到的下一个序号
    expect_seq = 1
    # 用于回复ACK的学号异或值
    syn_val_reply = student_id ^ STUDENT_XOR_CODE

    while True:
        # 从队列中取出数据包
        msg = q.get()
        if msg is None:  # 收到None表示线程需要退出
            break

        fields, data_str = parse_packet(msg)
        try:
            seq = int(fields.get("SeqNum", 0))
            data_received = data_str

            # 获取当前时间戳
            curr_time = time.strftime("%H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}"
            print(f"[{curr_time}]  收到数据 | 序列号={seq} | 期望={expect_seq}")
            print(f"  ← 收到报文: {packet_summary(msg)}")
            write_log(f"收到数据 | 序列号={seq} | 来自 {client_addr} | {packet_summary(msg)}")

            # 累积确认逻辑：
            # 如果收到的序号小于等于期望序号，说明是有效数据，更新期望值
            if seq <= expect_seq:
                expect_seq = max(expect_seq, seq + 1)
                ack_seq = expect_seq - 1
                ack_msg = make_packet(syn_val_reply, 3, 0, ack_seq, 0, "ACK")
                server_socket.sendto(ack_msg.encode(), client_addr)
                curr_time = time.strftime("%H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}"
                print(f"[{curr_time}]  累积确认 | ACK={ack_seq}")
                print(f"  → 发送报文: {packet_summary(ack_msg)}")
                write_log(f"累积确认 | ACK={ack_seq} | 来自 {client_addr} | {packet_summary(ack_msg)}")
            else:
                # 收到的序号大于期望，说明有丢包，回复重复的ACK
                ack_seq = expect_seq - 1
                ack_msg = make_packet(syn_val_reply, 3, 0, ack_seq, 0, "ACK")
                server_socket.sendto(ack_msg.encode(), client_addr)
                curr_time = time.strftime("%H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}"
                print(f"[{curr_time}]  乱序，重复确认 | ACK={ack_seq}")
                print(f"  → 发送报文: {packet_summary(ack_msg)}")
                write_log(f"乱序，重复确认 | ACK={ack_seq} | 来自 {client_addr} | {packet_summary(ack_msg)}")
        except Exception:
            pass


def get_current_time_str():
    # 获取当前时间戳（精确到毫秒）
    time_str = time.strftime("%H:%M:%S.", time.localtime())
    ms = int(time.time() * 1000) % 1000
    return time_str + f"{ms:03d}"

def main():

    # 创建socket并绑定端口
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((SERVER_IP, SERVER_PORT))
    
    # 打印服务端配置信息
    print("=" * 60)
    print("UDP 可靠传输服务端已启动")
    print(f"监听地址: {SERVER_IP}:{SERVER_PORT}")
    print(f"模拟丢包率: {PACKET_LOSS_RATE*100:.0f}%")
    print(f"校验异或值: {hex(STUDENT_XOR_CODE)}")
    print("=" * 60)
    write_log(f"服务端启动，监听 {SERVER_IP}:{SERVER_PORT}，丢包率 {PACKET_LOSS_RATE*100:.0f}%")
    print()

    while True:
        # 接收客户端数据
        data, client_addr = server_socket.recvfrom(BUFFER_SIZE)
        msg = data.decode("utf-8", errors="ignore")

        fields, data_str = parse_packet(msg)
        msg_type = fields.get("MsgType")
        flags = fields.get("Flags", "")

        # 处理三次握手
        # 第一次握手：收到SYN包
        if msg_type == "1" and flags == "SYN":
            try:
                syn_val = int(fields.get("StudentID", 0))
                # 通过异或还原学号后4位
                real_student_id = syn_val ^ STUDENT_XOR_CODE
                
                # 验证学号是否有效
                if 0 <= real_student_id <= 9999:
                    log_msg = f"客户端连接成功 | 学号后4位: {real_student_id:04d}"
                    print(f"[{get_current_time_str()}]  第1步 - 收到 SYN，学号验证通过")

                    # 处理同一客户端重复连接
                    # 如果该客户端已有连接，先清理旧连接
                    with client_queues_lock:
                        if client_addr in client_queues:
                            # 发送退出信号给旧线程
                            old_q = client_queues[client_addr]
                            old_q.put(None)
                            # 等待旧线程结束
                            if client_addr in client_threads:
                                client_threads[client_addr].join(timeout=1.0)
                            # 删除旧数据
                            del client_queues[client_addr]
                            del client_threads[client_addr]
                            print(f"[{get_current_time_str()}]  已清理客户端 {client_addr} 的旧连接")

                        # 创建新的消息队列和处理器线程
                        q = queue.Queue()
                        t = threading.Thread(target=client_handler, args=(client_addr, q, real_student_id, server_socket), daemon=True)
                        t.start()
                        client_queues[client_addr] = q
                        client_threads[client_addr] = t

                    # 发送第二次握手：SYN+ACK
                    reply_syn_val = real_student_id ^ STUDENT_XOR_CODE
                    reply = make_packet(reply_syn_val, 1, 0, 1, 0, "SYN+ACK")
                    print(f"[{get_current_time_str()}]  第2步 - 回复 SYN-ACK")
                    print(f"  → 发送报文: {packet_summary(reply)}")
                    server_socket.sendto(reply.encode(), client_addr)
                    write_log(log_msg)
                else:
                    # 学号无效，拒绝连接
                    print(f"[{get_current_time_str()}] 客户端校验失败，拒绝连接")
                    write_log(f"客户端校验失败，拒绝连接 {client_addr}")
                    server_socket.sendto(b"REFUSE", client_addr)
            except:
                server_socket.sendto(b"REFUSE", client_addr)
            continue

        # 第三次握手：收到ACK包
        if msg_type == "1" and flags == "ACK":
            print(f"[{get_current_time_str()}]  第3步 - 收到 ACK，三次握手完成")
            print(f"  ← 收到报文: {packet_summary(msg)}")
            write_log(f"收到 ACK，三次握手完成 | {packet_summary(msg)}")
            continue

        # ==================== 处理数据包 ====================
        # 模拟丢包：根据丢包率随机丢弃数据包
        if msg_type == "2" and random.random() < PACKET_LOSS_RATE:
            seq_num = fields.get("SeqNum", "?")
            print(f"[{get_current_time_str()}]  服务端模拟丢包 | seq={seq_num} | 来自 {client_addr}")
            write_log(f"模拟丢包 | seq_num={seq_num} | 来自 {client_addr}")
            continue

        # 将数据包转发到对应客户端的消息队列
        if msg_type == "2":
            with client_queues_lock:
                q = client_queues.get(client_addr)
                if q:
                    q.put(msg)


if __name__ == "__main__":
    main()

