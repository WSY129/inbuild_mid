"""
SQLite 기반 DB 설정.
이 백엔드는 '회원가입 정보'는 저장하지 않고(회원가입팀 소유),
홈/설정 화면에서만 쓰는 로컬 데이터(알림 설정 등)만 자체 DB에 저장한다.
"""
from sqlalchemy import create_engine
#create_engine: SQLAlchemy의 헬퍼. DB(SQLite)와 연결을 관리하는 엔진 객체 생성

from sqlalchemy.orm import sessionmaker, declarative_base
#sessionmaker: 쿼리 실행, 커밋 등 DB와 대화하는 통로인 세션 객체를 생성하는 팩토리 함수를 가져옴
#declarative_base: SQLAlchemy ORM을 쓰기 위해 테이블 클래스의 부모가 되는 베이스 클래스 생성
#-> 이 클래스를 상속받은 클래스는 SQLAlchemy가 테이블로 인식하고, DB에 반영할 수 있음

from app.config import settings


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite + FastAPI 멀티스레드 대응
    #원래 SQLite는 기본적으로 생성한 스레드에서만 DB에 접근 가능하도록 제한(check_same_thread=True)되어 있음
    # FastAPI는 요청마다 스레드가 달라질 수 있으므로, check_same_thread=False로 설정하여 멀티스레드 환경에서도 SQLite에 접근 가능하도록 함
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#세션을 생성하는 팩토리 -> SessionLocal()을 호출할 때마다 새 DB 세션 생성됨
#autocommit=False: 세션이 자동으로 커밋되지 않도록 설정. 명시적으로 db.commit() 호출해야 변경사항이 DB에 반영됨
#autoflush=False: 세션이 자동으로 flush되지 않도록 설정. flush는 대기중인 변경사항을 DB에 미리 전송하는 것. 명시적으로 db.flush() 호출해야 반영됨
#bind=engine: 이 세션이 위에서 만든 engine과 연결되도록 지정

Base = declarative_base()   #ORM 테이블 클래스의 부모가 되는 베이스 클래스 생성

#의존성 주입 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
