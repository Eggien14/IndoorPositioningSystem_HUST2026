from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine    

db_url = "mysql+pymysql://root:123456@127.0.0.1:3306/server"

engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit = False, autoflush = False, bind = engine)
