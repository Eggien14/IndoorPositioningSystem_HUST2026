from database import SessionLocal



# HÀM DEPENDENCY LẤY DB SESSION CHO CÁC API
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()