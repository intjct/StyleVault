# StyleVault (คลังสไตล์)

โปรแกรม Windows ฟรี ทำงานในเครื่อง เก็บคลิปจากช่างตัดต่อเก่งๆ (TikTok / YouTube Shorts / Instagram Reels / Facebook)
ไว้ในคลัง แสดงเป็นการ์ดพร้อมยอดวิว เพื่อให้ Claude วิเคราะห์สไตล์แล้วนำไปใช้ตัดต่อด้วย Remotion

แผนทั้งหมดอยู่ใน `plans/style-library-plan.md` ของ Project "Windows Tools"

## เวอร์ชัน
| เวอร์ชัน | สิ่งที่ได้ |
|---|---|
| 0.1.0 | หน้าคลัง (การ์ดเท่ากัน), วางลิงก์โหลดคลิป + ยอดวิว, ลากไฟล์มาวาง, หน้ารายละเอียด + โน้ต, ตั้งค่าที่เก็บคลัง |

## สร้างเอง (สำหรับนักพัฒนา)
```
pip install -r requirements.txt pytest
python -m pytest tests
python run.py
```
GitHub Actions สร้าง `.exe` + ตัวติดตั้งให้เองทุกครั้งที่ push เข้า `main` (ดูหน้า Releases)

ฟอนต์ Prompt: SIL Open Font License (`assets/fonts/OFL.txt`)
