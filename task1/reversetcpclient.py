import socket
import struct
import random
import sys
import os
import time
from datetime import datetime

# 获取脚本自身所在目录，确保日志写入共享文件夹
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "run_log.txt")
LOCK_FILE = os.path.join(BASE_DIR, "run_log.lock")

def write_log(info):
    deadline = time.time() + 3
    while True:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.time() > deadline:
                try:
                    os.remove(LOCK_FILE)
                except FileNotFoundError:
                    pass
                deadline = time.time() + 3
            else:
                time.sleep(0.005)
    try:
        t = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{t}]client:{info}\n")
    finally:
        os.remove(LOCK_FILE)

def main():
    if len(sys.argv) != 6:
        print("用法: python reversetcpclient.py IP PORT LMIN LMAX SEED")
        print("示例: python reversetcpclient.py 127.0.0.1 9999 30 100 1")
        return
    host = sys.argv[1]
    port = int(sys.argv[2])
    Lmin = int(sys.argv[3])
    Lmax = int(sys.argv[4])
    seed = int(sys.argv[5])

    random.seed(seed)  # 固定种子确保每次运行分块序列一致

    # 读取测试文件
    with open("test.txt", "r", encoding="ascii") as f:
        raw_all = f.read()
    raw_bytes = raw_all.encode("ascii")
    total_len = len(raw_bytes)

    # 随机分块：每块长度 [Lmin, Lmax]，最后一块为剩余字节
    chunk_list = []
    pos = 0
    while pos < total_len:
        remain = total_len - pos
        if remain <= Lmax:
            chunk_list.append(remain)
            pos += remain
        else:
            one = random.randint(Lmin, Lmax)
            chunk_list.append(one)
            pos += one
    N = len(chunk_list)
    write_log(f"总文件字节:{total_len},分块数量N={N},各块长度:{chunk_list}")

    #连接服务端
    cli = socket.socket()
    cli.connect((host, port))
    write_log(f"客户端连接{host}:{port},Lmin={Lmin},Lmax={Lmax},seed={seed},总块N={N}")

    # 发送初始化报文：Type=1 + 总块数N
    init_pkg = struct.pack(">HI", 1, N)
    cli.sendall(init_pkg)
    write_log(f"发送初始化报文Type=1,N={N}")

    # 接收服务端同意报文 Type=2
    agree_buf = cli.recv(2)
    agree_t = struct.unpack(">H", agree_buf)[0]
    write_log(f"收到agree报文Type={agree_t}")

    # 逐块发送数据请求、接收反转结果
    all_rev_data = b""
    offset = 0

    for idx, size in enumerate(chunk_list):
        block_data = raw_bytes[offset: offset + size]
        offset += size

        # 发送请求报文：Type=3 + 数据长度 + 数据
        req_head = struct.pack(">HI", 3, size)
        req_pkg = req_head + block_data
        cli.sendall(req_pkg)
        write_log(f"发送第{idx + 1}块请求Type=3,数据长度{size}")

        # 接收应答报文：Type=4 + 数据长度 + 反转数据
        ans_t_buf = cli.recv(2)
        ans_t = struct.unpack(">H", ans_t_buf)[0]
        ans_len_buf = cli.recv(4)
        ans_len = struct.unpack(">I", ans_len_buf)[0]
        rev_block = cli.recv(ans_len)
        all_rev_data += rev_block
        print(f"第{idx + 1}块:{rev_block.decode('ascii')}")
        write_log(f"收到第{idx + 1}块应答Type={ans_t},反转数据:{rev_block.decode('ascii')}")

    # 写入最终反转结果文件
    with open("result_rev.txt", "w", encoding="ascii") as f:
        f.write(all_rev_data.decode("ascii"))
    write_log("全部数据接收完成，已生成result_rev.txt完整反转文件\n")
    cli.close()

if __name__ == "__main__":
    main()
