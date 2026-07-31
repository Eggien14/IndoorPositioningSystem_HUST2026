1: Wifi 3 -> 1 vòng theo chiều kim đồng hồ, chiều dài bước chân ngẫu nhiên

TRAJECTORY_CELLS = [31, 32, 33, 34, 35, 30, 25, 20, 19, 14, 9, 8, 7, 12, 17, 16, 21, 26, 31]
Bo du lieu #test_case_1
So luong tin nhan: 2,797
Thoi diem tin nhan dau tien: 2026-05-03 13:22:09.160
Thoi diem tin nhan cuoi cung: 2026-05-03 13:23:29.210
Thoi gian tu dau den cuoi: 80.050 giay
Toc do tin nhan trung binh: 34.941 tin nhan/giay



2: Wifi 3 -> 1 vòng theo chiều kim đồng hồ, chiều dài bước chân 0.7m

Bo du lieu #test_case_2
So luong tin nhan: 3,064
Thoi diem tin nhan dau tien: 2026-05-03 13:27:32.449
Thoi diem tin nhan cuoi cung: 2026-05-03 13:28:59.919
Thoi gian tu dau den cuoi: 87.470 giay
Toc do tin nhan trung binh: 35.029 tin nhan/giay



3: 31->19->9->7->17->35->31 chiều dài bước chân 0.7m

Bo du lieu #test_case_3
So luong tin nhan: 2,892
Thoi diem tin nhan dau tien: 2026-05-03 13:35:41.872
Thoi diem tin nhan cuoi cung: 2026-05-03 13:37:09.528
Thoi gian tu dau den cuoi: 87.656 giay
Toc do tin nhan trung binh: 32.993 tin nhan/giay
CSV dòng 1 -> 2309 khớp với MQTTX group test_case_3 dòng 1 -> 2309
CSV dòng 2310 -> 2487 là 178 dòng không tồn tại trong Target tracking.json
CSV dòng 2488 -> 3070 khớp tiếp với MQTTX group dòng 2310 -> 2892

Bo du lieu #test_case_3_1
So luong tin nhan: 5,428
Thoi diem tin nhan dau tien: 2026-05-03 13:54:07.058
Thoi diem tin nhan cuoi cung: 2026-05-03 13:56:42.393
Thoi gian tu dau den cuoi: 155.335 giay
Toc do tin nhan trung binh: 34.944 tin nhan/giay



4: 31->19->9->7->17->35->31 chiều dài bước chân ngẫu nhiên

Bo du lieu #test_case_4
So luong tin nhan: 1,562
Thoi diem tin nhan dau tien: 2026-05-03 13:52:00.563
Thoi diem tin nhan cuoi cung: 2026-05-03 13:52:45.069
Thoi gian tu dau den cuoi: 44.506 giay
Toc do tin nhan trung binh: 35.096 tin nhan/giay



5: 31->19;20->35->17,16->31 bước chân 0.7m

Bo du lieu #test_case_5
So luong tin nhan: 2,314
Thoi diem tin nhan dau tien: 2026-05-03 13:47:22.699
Thoi diem tin nhan cuoi cung: 2026-05-03 13:48:28.905
Thoi gian tu dau den cuoi: 66.206 giay
Toc do tin nhan trung binh: 34.952 tin nhan/giay



6: 32->7->9->34->33 bước chân ngẫu nhiên

Bo du lieu #test_case_6
So luong tin nhan: 1,847
Thoi diem tin nhan dau tien: 2026-05-03 13:49:09.803
Thoi diem tin nhan cuoi cung: 2026-05-03 13:50:02.583
Thoi gian tu dau den cuoi: 52.780 giay
Toc do tin nhan trung binh: 34.994 tin nhan/giay



7: 31->19->9->7->17->35->20->16->31,32->7->9->34,33 bước chân 0.7

Bo du lieu #test_case_7
So luong tin nhan: 3,900
Thoi diem tin nhan dau tien: 2026-05-03 14:01:24.012
Thoi diem tin nhan cuoi cung: 2026-05-03 14:03:16.051
Thoi gian tu dau den cuoi: 112.039 giay
Toc do tin nhan trung binh: 34.809 tin nhan/giay
CSV dòng 3901 -> 4298 là 398 dòng dư so với MQTTX và không tìm thấy trong Target tracking.json