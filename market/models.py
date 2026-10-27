from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Profile(models.Model):
    METHODS = [('kakao', '카카오톡 오픈채팅'), ('discord', '디스코드'), ('email', '연락용 이메일')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    nickname = models.CharField('활동 이름', max_length=20)
    contact_method = models.CharField('연락 방법', max_length=10, choices=METHODS, blank=True)
    contact = models.CharField('비공개 연락처', max_length=200, blank=True)

    @property
    def has_contact(self):
        return bool(self.contact_method and self.contact)


class Listing(models.Model):
    JOBS = [('전사', '전사'), ('도적', '도적'), ('주술사', '주술사'), ('도사', '도사')]
    class Status(models.TextChoices):
        OPEN = 'open', '제안 받는 중'
        MATCHED = 'matched', '매칭 완료'
        IN_PROGRESS = 'in_progress', '진행 중'
        COMPLETED = 'completed', '완료'
        CANCELLED = 'cancelled', '취소'
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='listings')
    server = models.CharField(max_length=10, choices=[('태초', '태초')], default='태초')
    job = models.CharField('직업', max_length=10, choices=JOBS)
    title = models.CharField('의뢰 제목', max_length=60)
    level = models.CharField('현재 레벨 / 승급', max_length=50)
    goal = models.CharField('목표', max_length=80)
    price = models.CharField('희망 가격', max_length=80)
    available = models.CharField('가능 시간', max_length=100)
    detail = models.TextField('상세 조건', max_length=2000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    selected_offer = models.ForeignKey('Offer', null=True, blank=True, on_delete=models.SET_NULL, related_name='selected_for')
    version = models.PositiveIntegerField(default=1)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['is_hidden', 'status', 'job'])]
    def __str__(self):
        return self.title


class Offer(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='offers')
    knight = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='offers')
    amount = models.PositiveIntegerField('제안 금액 (원)', validators=[MinValueValidator(1), MaxValueValidator(1_000_000_000)])
    unit = models.CharField('가격 기준', max_length=10, choices=[('total', '총액'), ('per100m', '억당')])
    available = models.CharField('작업 가능 시간', max_length=100)
    detail = models.TextField('제안 조건', max_length=1000)
    listing_version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['created_at', 'pk']
        constraints = [models.UniqueConstraint(fields=['listing', 'knight'], name='one_offer_per_knight'), models.CheckConstraint(condition=models.Q(amount__gte=1, amount__lte=1_000_000_000), name='offer_amount_range')]


class Report(models.Model):
    REASONS = [('fraud', '사기 의심'), ('privacy', '개인정보 노출'), ('spam', '광고 / 도배'), ('abuse', '욕설 / 부적절한 내용'), ('other', '기타')]
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='reports')
    listing = models.ForeignKey(Listing, null=True, on_delete=models.SET_NULL, related_name='reports')
    # Retain only the reported public content if the author deletes the listing.
    snapshot = models.TextField()
    reason = models.CharField('신고 사유', max_length=10, choices=REASONS)
    detail = models.TextField('상세 내용', max_length=1000)
    status = models.CharField(max_length=10, choices=[('open', '접수'), ('resolved', '처리 완료'), ('dismissed', '반려')], default='open')
    response = models.TextField('처리 메모', max_length=1000, blank=True)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='handled_reports')
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    listing = models.ForeignKey(Listing, null=True, on_delete=models.SET_NULL)
    listing_id_snapshot = models.PositiveIntegerField()
    action = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)


class RateBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
