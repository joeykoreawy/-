# PythonAnywhere 무료 배포 안내

유료 서비스나 별도 도메인 구매 없이 `사용자명.pythonanywhere.com`으로 시작합니다. DB는 호스팅 서버의 영구 디스크에 저장되는 SQLite입니다. SQLite 파일을 사용자 PC마다 복사하는 방식이 아니며, 모든 접속자가 같은 서버 DB를 사용합니다.

## 확인한 무료 조건

2026-10-27에 PythonAnywhere 공식 문서 저장소의 `FreeAccountsFeatures.md`를 확인했습니다.

- 무료 계정: 웹앱 1개, 웹 워커 1개, 저장 공간 512MiB, 콘솔 2개, CPU seconds 100
- 웹앱 만료 1개월: Web 탭의 만료일과 연장/재활성화 항목을 관리해야 합니다. 무기한 무인 운영을 보장하지 않습니다.
- 2026-01-15 이후 신규 무료 계정은 MySQL과 정기 예약 작업을 제공하지 않습니다. 이 프로젝트는 둘 다 필요하지 않습니다. DB는 SQLite, 유지 관리는 콘솔에서 실행합니다.
- 초기 소규모 운영에 적합합니다. 트래픽·데이터 증가 시 백업 후 호스팅 및 PostgreSQL 등 DB 이전을 별도 검토해야 합니다.
- 무료 제공 조건은 바뀔 수 있으므로 가입 화면에서 다시 확인하세요. 유료 업그레이드·카드 등록은 이 절차에 필요하지 않습니다.

공식 근거:

- https://github.com/pythonanywhere/help_pages/blob/5e5f1ac5fccb805e6c09466f636033a6755c7733/articles/FreeAccountsFeatures.md
- https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/
- https://help.pythonanywhere.com/pages/FreeAccountsFeatures/

공식 사이트 직접 요청은 이 개발 환경의 프록시에서 403으로 차단되어 공식 GitHub 사본을 확인했습니다. 호스팅 계정 생성이나 외부 배포는 아직 실행하지 않았습니다.

## 1. 무료 계정 만들기

https://www.pythonanywhere.com/ 에서 무료 계정을 선택합니다. 계정 비밀번호와 인증코드는 본인만 보관하세요. 채팅에는 **사용자명만** 알려주면 이후 경로와 설정을 맞춰 안내할 수 있습니다.

이하 `YOUR_USERNAME`은 실제 사용자명으로 모두 바꿉니다. EU 시스템 계정이라면 대시보드에서 배정받은 실제 호스트를 사용하세요.

## 2. 소스 올리기

제공된 `jakji-site.zip`을 Files 탭에서 `/home/YOUR_USERNAME/`에 업로드합니다. 이 파일에는 소스만 있고 비밀키·회원 데이터·DB·가상환경은 없습니다.

Consoles → Bash를 열어 실행합니다:

```bash
cd /home/YOUR_USERNAME
python3 -m zipfile -e jakji-site.zip .
cd jakji
```

압축은 `jakji/` 디렉터리 아래에 풀립니다. `manage.py`가 `/home/YOUR_USERNAME/jakji/manage.py`인지 확인합니다. ZIP이 아닌 Git을 이용하는 경우에는 소스를 먼저 사용자 저장소에 반영해야 합니다. 현재 원격 저장소에는 자동으로 push하지 않았습니다.

## 3. 설치와 비공개 설정

콘솔에 있는 Python 버전을 확인하고, Web 탭에서 선택할 것과 동일한 버전을 사용합니다. 아래는 Python 3.12 예시입니다.

```bash
cd /home/YOUR_USERNAME/jakji
PYTHON_BIN=python3.12 WEBSITE_HOST=YOUR_USERNAME.pythonanywhere.com bash scripts/setup.sh
```

Files 탭에서 `jakji/.local/environment`를 엽니다. 숨김 파일 표시가 필요할 수 있습니다. `DJANGO_SECRET_KEY`는 자동 생성된 값을 유지하고, 아래 항목을 확인·수정합니다:

```text
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=YOUR_USERNAME.pythonanywhere.com
DJANGO_HTTPS=1
DJANGO_CSRF_TRUSTED_ORIGINS=https://YOUR_USERNAME.pythonanywhere.com
OPERATOR_CONTACT=운영 문의용 이메일 또는 오픈채팅 URL
```

운영 문의 연락처는 사이트 이용 안내에 공개됩니다. 여기에 계정 비밀번호나 게임 인증정보를 넣지 마세요. `.local/environment`와 DB를 GitHub나 정적 파일 경로에 올리지 마세요.

운영자를 생성합니다 (비밀번호는 콘솔이 숨겨서 입력받습니다):

```bash
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py check_public
```

설정 오류가 있으면 `check_public`이 실패합니다. 모든 오류를 해결하고 진행합니다.

## 4. 무료 웹앱 연결

1. Web → Add a new web app → 배정된 무료 도메인 → **Manual configuration**을 선택합니다. 새 Django 프로젝트 생성 옵션을 선택하지 마세요.
2. 3단계와 동일한 Python 버전을 선택합니다.
3. Source code / Working directory: `/home/YOUR_USERNAME/jakji`
4. Virtualenv: `/home/YOUR_USERNAME/jakji/.venv`
5. Web 탭에서 연결된 **WSGI configuration file**을 열고 아래로 교체합니다 (프로젝트 내부의 `config/wsgi.py`가 아닙니다):

```python
import os
import sys

project_path = '/home/YOUR_USERNAME/jakji'
if project_path not in sys.path:
    sys.path.insert(0, project_path)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

6. Static files에 URL `/static/`, Directory `/home/YOUR_USERNAME/jakji/staticfiles`를 연결합니다. `.local/` 또는 프로젝트 전체를 Static files로 연결하면 안 됩니다.
7. HTTPS 강제 옵션이 표시되면 활성화합니다. 애플리케이션도 HTTPS를 강제합니다.
8. Reload를 누릅니다. 오류가 있으면 Web 탭의 Error log를 확인합니다. 비밀키나 로그 전체를 공개 채팅에 붙이지 마세요.

PythonAnywhere에서는 `runserver`나 `scripts/start.sh`를 콘솔에서 계속 켜두지 않습니다. Web 탭의 WSGI 워커가 앱을 실행합니다.

## 5. 공개 URL 검증

새 배포 환경에서 다음을 별도로 확인해야 합니다. 개발 환경에서 통과한 결과가 배포 환경의 성공을 보장하지는 않습니다.

1. 배정된 HTTPS 주소가 열리고 `/health/`가 `ok`를 반환하는지 확인합니다.
2. PC의 일반 창과 시크릿 창에서 서로 다른 일반 계정 A와 B를 가입합니다. 게임 계정 비밀번호를 재사용하지 마세요.
3. 각 계정의 내 정보에서 테스트용 연락처를 설정합니다.
4. A가 의뢰를 등록하고 B·비로그인 창에서 같은 글이 보이는지 확인합니다.
5. B가 가격을 제안하고 A가 기사를 선택합니다.
6. A·B에게만 서로의 연락처가 보이는지, 비로그인과 미선택 계정에게는 보이지 않는지 확인합니다.
7. 다른 계정으로 수정·삭제 주소에 접근해도 거부되는지 확인합니다.
8. B가 작업을 시작하고 A가 완료를 확인합니다.
9. 신고를 접수하고 운영자가 처리할 수 있는지 확인합니다.
10. Reload 후에도 회원과 게시 데이터가 남아 있는지 확인합니다.

두 테스트 계정은 실제 회원과 혼동되지 않게 표시하고, 점검 후 비공개 연락처를 삭제하세요.

## 6. 정기 운영

무료 플랜에서는 예약 작업을 전제로 하지 않습니다. [운영 안내](OPERATIONS.md)의 백업·기록 정리 명령을 콘솔에서 정기적으로 실행하고, Web 탭의 만료일을 확인합니다. 백업을 외부의 안전한 저장 위치에도 보관하세요. 무료 호스팅의 가용성과 디스크 한도 안에서 운영해야 합니다.
