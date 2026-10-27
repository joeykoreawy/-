# 운영·백업

명령은 프로젝트 루트에서 실행합니다. `.local/`은 비공개이며 DB 파일과 설정을 외부에 공개하지 마세요. 테스트 DB는 `.local/e2e/`, 실제 서비스 DB는 `.local/db.sqlite3`로 분리되어 있습니다.

## 권한 관리

- 초기 운영자는 `.venv/bin/python manage.py createsuperuser`로 생성합니다.
- 슈퍼유저는 `/admin/`에서 필요한 운영자만 `is_staff`로 지정할 수 있습니다. 일반 회원에게 해당 권한을 주지 마세요.
- 운영자의 신고 관리 주소: `/operations/reports/`. 처리 메모는 신고자에게 공개됩니다. 숨김/복원은 감사 기록에 남습니다.
- 연락처·제안은 Django 관리자에 일괄 조회 모델로 등록하지 않았습니다. DB와 서버 파일 접근 권한 자체는 신뢰할 수 있는 운영자에게만 부여해야 합니다.
- 사이트 비밀번호 분실 시 자동 이메일 복구는 없습니다. 운영자가 별도로 본인 확인 후 `.venv/bin/python manage.py changepassword USERNAME`으로 초기화합니다. 새 비밀번호는 채팅이나 공개 로그에 남기지 마세요.

## DB 백업

```bash
.venv/bin/python scripts/backup.py
```

실행 중인 DB도 SQLite online backup API로 일관된 스냅샷을 저장합니다. `.local/backups/`에 최근 7개만 유지합니다. 백업에는 개인정보가 있으므로 안전한 별도 위치에 주기적으로 내려받아 보관하고, 보관 필요가 끝난 사본은 삭제하세요. 무료 호스팅에는 자동 예약 작업이 없으므로 가입 플랜에서 제공되지 않는 기능을 전제로 하지 않습니다.

복구할 때는 **사이트를 먼저 중단**합니다. PythonAnywhere Web 탭에서 Disable webapp을 사용하거나, 별도 서버라면 앱 프로세스를 중단합니다. 현재 DB도 백업하고, 선택한 백업을 `.local/db.sqlite3`로 복사한 뒤 `.venv/bin/python manage.py migrate --noinput`을 실행합니다. 올바른 계정·글·신고가 복구됐는지 확인하고 다시 활성화/Reload합니다. 사용 중인 파일 위에 복사하지 마세요.

## 보관 기간과 계정 탈퇴

주 1회 및 배포 시 실행을 권장합니다. 운영자가 실제 실행 일정을 책임져야 합니다.

```bash
.venv/bin/python manage.py prune_records
.venv/bin/python manage.py clearsessions
```

처리 완료 신고는 처리일 기준 90일, 감사 기록은 180일 경과 후 삭제합니다. 미처리 신고는 자동 삭제하지 않습니다. 만료된 임시 요청 제한 기록도 삭제합니다. 과거 백업에 남은 정보는 백업 보관 정책에 따라 함께 삭제해야 합니다.

탈퇴 요청은 운영 문의 연락처로 접수하고 본인 확인 후 백업·분쟁 보존 필요를 판단합니다. 실행 명령:

```bash
.venv/bin/python manage.py anonymize_user USERNAME --confirm
```

로그인 불가, 사이트 비밀번호 무효화, 연락처/기존 활동 이름/아이디 제거, 해당 회원의 의뢰 비공개, 진행 중 매칭 취소를 수행합니다. 다른 회원의 기록을 보호하기 위해 참조 ID와 익명화된 완료·신고 기록이 남을 수 있습니다. 운영자 계정은 해당 명령으로 익명화되지 않으며 먼저 관리 권한을 인계해야 합니다.

## 업데이트

1. DB와 `.local/environment`를 비공개로 백업합니다.
2. 새 코드만 덮어쓰고 `.local/`과 `.venv/`는 보존합니다.
3. `bash scripts/setup.sh`로 의존성·마이그레이션·정적 파일을 갱신합니다.
4. `.venv/bin/python manage.py test`와 `check_public`을 실행합니다.
5. Web 탭에서 Reload 후 공개 주소의 핵심 흐름을 다시 확인합니다.

서버를 여러 대로 늘리거나 SQLite 파일을 네트워크로 공유하는 구성은 이 초기 버전에 포함하지 않습니다. 그 단계에서는 PostgreSQL과 공유된 요청 제한 저장소를 검토합니다.
