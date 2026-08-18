"""
설정 화면에 있는 버튼 파일들(update_어쩌고.py)이 공통으로 쓰는 헬퍼.
버튼 파일 자체는 아니므로 라우터를 등록하지 않음.
update_어쩌고.py에서 공통으로 쓰는 로직들을 모아둔 파일
"""
from sqlalchemy.orm import Session
#session: 파이썬과 DB가 SQL언어 안쓰고 대화하는 통로. DB에 쿼리문을 보내고, 결과를 받아오는 역할
#db를 session타입으로 받음으로써 db.get, db.add, db.commit, db.refresh 등 session이 제공하는 메서드를 사용할 수 있음 

from app.models.user_settings import UserSettings
#UserSettings 테이블에 접근하기 위해 import

from app.schemas.settings_schema import SettingsResponse
#SettingsResponse를 반환하기 위해 import

#user_internal_id는 blood_link.db의 users.id. 로그인 아이디가 아니다 (user_settings.py 주석 참고)
def get_or_create_settings(db: Session, user_internal_id: int) -> UserSettings:
    settings_row = db.get(UserSettings, user_internal_id)
    #아직 유저가 설정을 한 적이 없을 때 기본값 자동생성
    if settings_row is None:
        settings_row = UserSettings(user_internal_id=user_internal_id)
        db.add(settings_row)
        db.commit()
        db.refresh(settings_row)    #DB가 채워준 값 최신상태로 파이썬 객체에 반영
    return settings_row

#DB 안의 객체를 SettingsResponse로 변환하는 헬퍼
#-> 앱화면에 보여줄 수 있는 형태로 변환
def to_response(settings_row: UserSettings) -> SettingsResponse:
    return SettingsResponse(
        notification_enabled=settings_row.notification_enabled,
        sensitivity=settings_row.sensitivity,
        frequency=settings_row.frequency,
        resend_count=settings_row.resend_count,
    )
