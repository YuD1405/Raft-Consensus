# Raft-based Distributed System Simulator

## Giới thiệu
Dự án này triển khai một **mô phỏng hệ thống phân tán dựa trên thuật toán Raft** nhằm minh họa cơ chế **leader election, log replication, fault tolerance và network partition**.  
Hệ thống được xây dựng phục vụ mục đích **học tập, nghiên cứu và demo**, tập trung vào việc hiểu rõ bản chất hoạt động của Raft hơn là tối ưu hiệu năng.

## Mục tiêu
- Hiểu và hiện thực hóa thuật toán **Raft Consensus**
- Mô phỏng các tình huống thực tế:
  - Node crash / restart
  - Leader election
  - Network partition & heal
- Quan sát sự **nhất quán dữ liệu (consistency)** giữa các node
- Kết nối **Backend – Frontend** để hiển thị trạng thái hệ thống theo thời gian thực

## Kiến trúc tổng quát
Hệ thống gồm 3 thành phần chính:

- **Raft Node (Backend)**  
  - Mỗi node chạy độc lập
  - Giao tiếp qua RPC
  - Duy trì state: `Follower / Candidate / Leader`
  - Quản lý log, term, commit index

- **Cluster / Partition Layer**  
  - Giả lập phân mảnh mạng (partition)
  - Cho phép tách – gộp các nhóm node
  - Kiểm tra hành vi hệ thống khi mất kết nối

- **UI / Frontend**  
  - Hiển thị trạng thái các node
  - Theo dõi leader hiện tại, term, log
  - Nhận tín hiệu cập nhật từ backend (event-based)

## Các chức năng chính
- Leader Election theo Raft
- Heartbeat & timeout
- Log replication & commit
- Mô phỏng kill / revive node
- Network partition & heal
- Đồng bộ trạng thái sau khi merge partition

## Công nghệ sử dụng
- **Ngôn ngữ**: Python  
- **Concurrency**: Threading  
- **Giao tiếp**: RPC / gRPC (Protocol Buffers)  
- **Frontend**: UI đơn giản để visualize trạng thái hệ thống  
- **Môi trường**: Local simulation

## Cách chạy chương trình
### Cài đặt môi trường
1. Clone repository:
```bash
git clone https://github.com/YuD1405/Raft-Consensus.git
cd Raft-Consensus
```

2. Cài đặt các thư viện cần thiết:
```bash
pip install -r requirements.txt
```

3. Chạy hệ thống
Khởi động giao diện mô phỏng bằng Streamlit:
```bash
streamlit run main.py
```

4. Khởi tạo các Raft node
5. Chạy backend cho từng node
6. Khởi động frontend để theo dõi trạng thái
7. Thực hiện các thao tác:
   - Kill node
   - Gưi request từ Client
   - Tạo partition
   - Heal network
   - Ghi log mới và quan sát quá trình commit
  

## Kết quả đạt được
- Hệ thống bầu leader đúng theo Raft
- Đảm bảo **Leader Completeness** và **Log Matching**
- Khi heal partition, dữ liệu được đồng bộ dựa trên log hợp lệ
- UI phản ánh đúng trạng thái hệ thống theo thời gian thực
