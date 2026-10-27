from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import ContactForm, ListingForm, LoginForm, ModerationForm, OfferForm, ReportForm, SignupForm
from .models import AuditEvent, Listing, Offer, Profile, Report
from .security import limited


def error(request, message, status=409):
    return render(request, 'market/error.html', {'error': message}, status=status)


def profile(user):
    return Profile.objects.get_or_create(user=user, defaults={'nickname': user.username})[0]


def audit(user, listing, action):
    AuditEvent.objects.create(actor=user, listing=listing, listing_id_snapshot=listing.pk, action=action)


def visible(request, pk, lock=False):
    qs = Listing.objects.select_related('owner__profile', 'selected_offer__knight__profile')
    if lock:
        qs = qs.select_for_update()
    if not request.user.is_staff:
        access = Q(is_hidden=False)
        if request.user.is_authenticated:
            access |= Q(owner=request.user) | Q(selected_offer__knight=request.user)
        qs = qs.filter(access)
    return get_object_or_404(qs, pk=pk)


def home(request):
    listings = Listing.objects.filter(is_hidden=False).select_related('owner__profile').annotate(offer_count=Count('offers'))
    job = request.GET.get('job', '')
    if job in dict(Listing.JOBS):
        listings = listings.filter(job=job)
    else:
        job = ''
    state = request.GET.get('status', '')
    if state in dict(Listing.Status.choices):
        listings = listings.filter(status=state)
    else:
        state = ''
    query = request.GET.get('q', '').strip()[:100]
    if query:
        listings = listings.filter(Q(title__icontains=query) | Q(goal__icontains=query))
    from django.core.paginator import Paginator
    page = Paginator(listings.order_by('-created_at', '-pk'), 12).get_page(request.GET.get('page'))
    return render(request, 'market/home.html', {'page': page, 'jobs': Listing.JOBS, 'job': job, 'state': state, 'states': Listing.Status.choices, 'query': query, 'total': listings.count()})


class ThrottledLoginView(LoginView):
    template_name = 'market/auth.html'
    authentication_form = LoginForm
    extra_context = {'title': '다시 오셨군요', 'subtitle': '로그인하고 의뢰와 제안을 이어가세요.', 'submit': '로그인', 'mode': 'login'}
    def post(self, request, *args, **kwargs):
        if limited(request, 'login-ip', 60, 900) or limited(request, 'login-name', 12, 900, request.POST.get('username', '').lower()):
            return error(request, '로그인 시도가 많습니다. 15분 후 다시 시도해 주세요.', 429)
        return super().post(request, *args, **kwargs)


def signup(request):
    if request.user.is_authenticated:
        return redirect('account')
    if request.method == 'POST' and limited(request, 'signup', 10, 3600):
        return error(request, '가입 시도가 많습니다. 1시간 후 다시 시도해 주세요.', 429)
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                Profile.objects.create(user=user, nickname=form.cleaned_data['nickname'])
        except IntegrityError:
            form.add_error('username', '이미 사용 중인 아이디입니다.')
        else:
            login(request, user)
            messages.success(request, '가입을 환영합니다. 매칭에 사용할 비공개 연락처를 설정해 주세요.')
            return redirect('account')
    return render(request, 'market/auth.html', {'form': form, 'title': '모험의 인연을 시작해요', 'subtitle': '한 계정으로 의뢰인과 기사, 모두 활동할 수 있어요.', 'submit': '회원가입', 'mode': 'signup'})


@login_required
def account(request):
    form = ContactForm(request.POST or None, instance=profile(request.user))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '활동 이름과 비공개 연락처를 저장했습니다.')
        return redirect('account')
    return render(request, 'market/form.html', {'form': form, 'title': '내 정보', 'subtitle': '연락처는 매칭 후 해당 의뢰의 당사자에게만 표시됩니다. 비워서 삭제할 수 있습니다.', 'submit': '내 정보 저장', 'kind': 'account'})


@login_required
def mine(request):
    return render(request, 'market/mine.html', {'listings': request.user.listings.all(), 'offers': request.user.offers.select_related('listing').all(), 'reports': request.user.reports.select_related('listing').all()})


@login_required
def listing_create(request):
    if not profile(request.user).has_contact:
        messages.info(request, '먼저 내 정보에서 매칭 후 공개할 연락처를 등록해 주세요.')
        return redirect('account')
    if request.method == 'POST' and limited(request, 'create', 20, 3600, str(request.user.pk)):
        return error(request, '의뢰 등록이 많습니다. 1시간 후 다시 시도해 주세요.', 429)
    form = ListingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        listing = form.save(commit=False)
        listing.owner = request.user
        listing.save()
        audit(request.user, listing, 'create')
        messages.success(request, '의뢰가 등록되었습니다. 다른 사용자도 이 의뢰를 볼 수 있습니다.')
        return redirect('detail', pk=listing.pk)
    return render(request, 'market/form.html', {'form': form, 'title': '작지 의뢰 등록', 'subtitle': '태초에서 함께할 기사님을 만나 보세요.', 'submit': '의뢰 등록하기', 'kind': 'listing'})


def detail(request, pk):
    listing = visible(request, pk)
    owner = request.user.is_authenticated and listing.owner_id == request.user.pk
    chosen = bool(request.user.is_authenticated and listing.selected_offer_id and listing.selected_offer.knight_id == request.user.pk)
    offers = listing.offers.select_related('knight__profile')
    if not owner:
        offers = offers.filter(knight=request.user) if request.user.is_authenticated else offers.none()
    can_contact = (owner or chosen) and not listing.is_hidden and listing.status in [Listing.Status.MATCHED, Listing.Status.IN_PROGRESS, Listing.Status.COMPLETED]
    contact = None
    if can_contact:
        other = listing.selected_offer.knight if owner else listing.owner
        contact = profile(other)
    return render(request, 'market/detail.html', {'listing': listing, 'offers': offers, 'offer_count': listing.offers.count(), 'is_owner': owner, 'is_chosen': chosen, 'contact': contact, 'matched': listing.selected_offer if (owner or chosen) else None})


@login_required
def listing_edit(request, pk):
    with transaction.atomic():
        listing = get_object_or_404(Listing.objects.select_for_update(), pk=pk, owner=request.user)
        if listing.status != Listing.Status.OPEN:
            return error(request, '매칭 이후에는 의뢰 조건을 수정할 수 없습니다. 당사자와 협의하거나 의뢰를 취소해 주세요.')
        form = ListingForm(request.POST or None, instance=listing, initial={'edit_version': listing.version})
        if request.method == 'POST' and form.is_valid():
            if form.cleaned_data['edit_version'] != listing.version:
                return error(request, '다른 창에서 의뢰가 수정되었습니다. 새로 열어 다시 확인해 주세요.')
            listing = form.save(commit=False)
            listing.version += 1
            listing.save()
            audit(request.user, listing, 'edit')
            messages.success(request, '의뢰를 수정했습니다. 기존 제안은 기사가 새 조건을 확인하고 다시 저장해야 선택할 수 있습니다.')
            return redirect('detail', pk=listing.pk)
    return render(request, 'market/form.html', {'form': form, 'title': '의뢰 수정', 'subtitle': '조건이 바뀌면 기존 기사는 제안을 다시 확인해야 합니다.', 'submit': '수정 내용 저장', 'kind': 'listing'})


@login_required
def listing_delete(request, pk):
    with transaction.atomic():
        listing = get_object_or_404(Listing.objects.select_for_update(), pk=pk, owner=request.user)
        if listing.status not in [Listing.Status.OPEN, Listing.Status.CANCELLED]:
            return error(request, '매칭된 의뢰는 먼저 취소해 주세요. 완료된 의뢰는 진행 기록으로 보관됩니다.')
        if request.method == 'POST':
            audit(request.user, listing, 'delete')
            listing.delete()
            messages.success(request, '의뢰와 관련 제안을 삭제했습니다. 접수된 신고는 운영 기록으로 보관됩니다.')
            return redirect('mine')
    return render(request, 'market/confirm.html', {'title': '의뢰를 삭제할까요?', 'description': '관련 제안도 삭제되며 복구할 수 없습니다.', 'listing': listing, 'submit': '의뢰 삭제'})


@login_required
def offer_edit(request, pk):
    if request.method == 'POST' and limited(request, 'offer', 60, 3600, str(request.user.pk)):
        return error(request, '제안 저장 횟수가 많습니다. 1시간 후 다시 시도해 주세요.', 429)
    with transaction.atomic():
        listing = visible(request, pk, lock=True)
        if listing.owner_id == request.user.pk:
            return error(request, '본인 의뢰에는 제안할 수 없습니다.', 403)
        if listing.status != Listing.Status.OPEN or listing.is_hidden:
            return error(request, '현재 제안을 받는 의뢰가 아닙니다.')
        if not profile(request.user).has_contact:
            messages.info(request, '먼저 내 정보에서 매칭 후 공개할 연락처를 등록해 주세요.')
            return redirect('account')
        existing = Offer.objects.filter(listing=listing, knight=request.user).first()
        form = OfferForm(request.POST or None, instance=existing, initial={'version': listing.version})
        if request.method == 'POST' and form.is_valid():
            if form.cleaned_data['version'] != listing.version:
                return error(request, '의뢰 조건이 변경되었습니다. 의뢰를 다시 읽고 제안해 주세요.')
            offer = form.save(commit=False)
            offer.listing = listing
            offer.knight = request.user
            offer.listing_version = listing.version
            offer.save()
            audit(request.user, listing, 'offer')
            messages.success(request, '제안을 저장했습니다. 가격과 조건은 의뢰인과 본인에게만 보입니다.')
            return redirect('detail', pk=pk)
    return render(request, 'market/form.html', {'form': form, 'title': '기사로 제안하기', 'subtitle': listing.title, 'submit': '제안 저장', 'kind': 'offer'})


@login_required
@require_POST
def offer_withdraw(request, pk, offer_id):
    with transaction.atomic():
        listing = visible(request, pk, lock=True)
        offer = get_object_or_404(Offer, pk=offer_id, listing=listing, knight=request.user)
        if listing.status != Listing.Status.OPEN:
            return error(request, '매칭 이후에는 제안을 철회할 수 없습니다.')
        offer.delete()
        audit(request.user, listing, 'withdraw')
    messages.success(request, '제안을 철회했습니다.')
    return redirect('detail', pk=pk)


@login_required
@require_POST
def select_offer(request, pk, offer_id):
    with transaction.atomic():
        listing = get_object_or_404(Listing.objects.select_for_update(), pk=pk, owner=request.user)
        offer = get_object_or_404(Offer.objects.select_related('knight__profile'), pk=offer_id, listing=listing)
        if listing.status != Listing.Status.OPEN or listing.is_hidden:
            return error(request, '이미 매칭되었거나 선택할 수 없는 의뢰입니다.')
        if offer.listing_version != listing.version:
            return error(request, '의뢰 수정 전 제안입니다. 기사님이 새 조건을 확인하고 제안을 저장해야 선택할 수 있습니다.')
        if not profile(request.user).has_contact or not profile(offer.knight).has_contact:
            return error(request, '당사자 모두 비공개 연락처를 등록해야 매칭할 수 있습니다.')
        listing.selected_offer = offer
        listing.status = Listing.Status.MATCHED
        listing.save(update_fields=['selected_offer', 'status', 'updated_at'])
        audit(request.user, listing, 'match')
    messages.success(request, '기사님을 선택했습니다. 이제 당사자끼리 연락처를 확인할 수 있습니다.')
    return redirect('detail', pk=pk)


@login_required
@require_POST
def change_status(request, pk):
    with transaction.atomic():
        listing = visible(request, pk, lock=True)
        owner = listing.owner_id == request.user.pk
        knight = bool(listing.selected_offer_id and listing.selected_offer.knight_id == request.user.pk)
        if not (owner or knight):
            return error(request, '당사자만 진행 상태를 변경할 수 있습니다.', 403)
        action = request.POST.get('action')
        old = listing.status
        if action == 'start' and knight and old == Listing.Status.MATCHED and not listing.is_hidden:
            listing.status = Listing.Status.IN_PROGRESS
        elif action == 'complete' and owner and old == Listing.Status.IN_PROGRESS and not listing.is_hidden:
            listing.status = Listing.Status.COMPLETED
        elif action == 'cancel' and old in [Listing.Status.OPEN, Listing.Status.MATCHED, Listing.Status.IN_PROGRESS]:
            listing.status = Listing.Status.CANCELLED
        else:
            return error(request, '허용되지 않는 상태 변경입니다. 기사가 작업을 시작하고 의뢰인이 완료를 확인합니다.')
        listing.save(update_fields=['status', 'updated_at'])
        audit(request.user, listing, action)
    messages.success(request, '진행 상태를 변경했습니다.')
    return redirect('detail', pk=pk)


@login_required
def report(request, pk):
    listing = visible(request, pk)
    if listing.owner_id == request.user.pk:
        return error(request, '본인 의뢰는 신고할 수 없습니다.', 403)
    if request.method == 'POST' and limited(request, 'report', 10, 86400, str(request.user.pk)):
        return error(request, '하루 신고 횟수를 초과했습니다. 내 활동에서 처리 결과를 확인해 주세요.', 429)
    form = ReportForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            listing = visible(request, pk, lock=True)
            if Report.objects.filter(listing=listing, reporter=request.user, status='open').exists():
                return error(request, '이미 접수된 신고입니다. 내 활동에서 처리 결과를 확인해 주세요.')
            item = form.save(commit=False)
            item.reporter, item.listing = request.user, listing
            item.snapshot = f'{listing.title}\n{listing.get_server_display()} · {listing.job}\n{listing.level}\n{listing.goal}\n{listing.price}\n{listing.available}\n{listing.detail}'
            item.save()
        messages.success(request, '신고를 접수했습니다. 운영자가 확인 후 처리합니다.')
        return redirect('mine')
    return render(request, 'market/form.html', {'form': form, 'title': '의뢰 신고', 'subtitle': listing.title, 'submit': '신고 접수', 'kind': 'report'})


@user_passes_test(lambda u: u.is_active and u.is_staff)
def moderation(request):
    items = Report.objects.select_related('listing', 'reporter__profile', 'handled_by')
    if request.GET.get('all') != '1':
        items = items.filter(status='open')
    from django.core.paginator import Paginator
    return render(request, 'market/moderation.html', {'page': Paginator(items, 20).get_page(request.GET.get('page'))})


@user_passes_test(lambda u: u.is_active and u.is_staff)
def moderate(request, pk):
    with transaction.atomic():
        item = get_object_or_404(Report.objects.select_for_update().select_related('listing'), pk=pk)
        form = ModerationForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            action = form.cleaned_data['action']
            if item.listing_id:
                listing = Listing.objects.select_for_update().get(pk=item.listing_id)
                if action in ['hide', 'restore']:
                    listing.is_hidden = action == 'hide'
                    listing.save(update_fields=['is_hidden'])
                    audit(request.user, listing, action)
            elif action in ['hide', 'restore']:
                return error(request, '이미 삭제된 의뢰는 공개 상태를 변경할 수 없습니다.')
            item.status = 'dismissed' if action == 'dismiss' else 'resolved'
            item.response = form.cleaned_data['response']
            item.handled_by = request.user
            item.handled_at = timezone.now()
            item.save()
            messages.success(request, '신고 처리 결과를 저장했습니다.')
            return redirect('moderation')
    return render(request, 'market/moderate.html', {'item': item, 'form': form})


def guide(request):
    from django.conf import settings
    return render(request, 'market/guide.html', {'operator_contact': settings.OPERATOR_CONTACT})


def health(request):
    # Check the actual database, not just the process.
    Listing.objects.exists()
    return HttpResponse('ok', content_type='text/plain')
