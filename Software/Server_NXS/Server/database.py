from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine    

import os

# Set DATABASE_URL, e.g. mysql+pymysql://<user>:<password>@127.0.0.1:3306/server
db_url = os.getenv("DATABASE_URL", "mysql+pymysql://root:@127.0.0.1:3306/server")

engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit = False, autoflush = False, bind = engine)
