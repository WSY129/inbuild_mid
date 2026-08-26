#!/bin/bash
# 홈/설정 서버(:8000)와 회원가입 서버(:8001)를 함께 띄운다.
#
# ⚠️ 두 서버는 blood_link.db 파일 하나를 공유한다.
#    회원가입팀 코드가 sqlite3.connect("blood_link.db") 상대경로를 쓰기 때문에,
#    반드시 이 폴더를 작업 디렉토리로 삼아 실행해야 같은 파일을 본다.
#    다른 위치에서 띄우면 빈 DB가 새로 생기고 가입한 사람이 안 보인다.

cd "$(dirname "$0")" || exit 1

SIGNUP_CODE=/Users/siyeon6002/Downloads/inbuild_mid-main
HOME_PORT=${HOME_PORT:-8000}
SIGNUP_PORT=${SIGNUP_PORT:-8001}

for p in $HOME_PORT $SIGNUP_PORT; do
  if lsof -ti:$p >/dev/null 2>&1; then
    echo "❌ 포트 $p 를 이미 쓰고 있습니다. 예전 서버를 먼저 끄세요:"
    echo "     lsof -ti:$p | xargs kill"
    exit 1
  fi
done

IP=$(ipconfig getifaddr en0 2>/dev/null || echo "IP확인불가")

# Ctrl+C(INT)든 다른 이유로 죽든(EXIT) 두 서버를 반드시 함께 정리한다.
# 트랩을 먼저 걸어둬야 기동 직후에 눌러도 자식이 안 남는다.
# trap을 즉시 해제해서 INT/TERM/EXIT가 겹쳐도 메시지가 두 번 찍히지 않게 한다
cleanup() { trap - INT TERM EXIT; echo; echo "서버를 종료합니다..."; kill $PID_HOME $PID_SIGNUP 2>/dev/null; }
trap cleanup INT TERM EXIT

./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $HOME_PORT &
PID_HOME=$!
PYTHONPATH="$SIGNUP_CODE" ./venv/bin/uvicorn main:app --host 0.0.0.0 --port $SIGNUP_PORT &
PID_SIGNUP=$!

sleep 3
echo
echo "════════════════════════════════════════════════════"
echo "  프론트한테 보낼 주소"
echo "════════════════════════════════════════════════════"
echo "   홈·설정        http://$IP:$HOME_PORT"
echo "   회원가입·로그인  http://$IP:$SIGNUP_PORT"
echo
echo "   내가 볼 API 문서 http://127.0.0.1:$HOME_PORT/docs"
echo "   끄기            이 창에서 Ctrl+C"
echo "════════════════════════════════════════════════════"
echo
wait
