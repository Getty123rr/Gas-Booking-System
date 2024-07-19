from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from accounts.tokens import account_activation_token
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.urls import reverse_lazy
import datetime
from django.contrib.auth import get_user_model
from .mixins import AictiveUserRequiredMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.contrib.auth.forms import PasswordChangeForm

from accounts.forms import SignUpForm, UserForm, ProfileForm, PaymentCreditCardForm
from accounts.models import Profile, PaymentCreditCard
from gas.models import Booking
from settings.models import Instruction


from django.views import View, generic
# Create your views here.
class LoginView(LoginView):
    template_name = 'landing/login.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'GasBooking'
        return context
    def render_to_response(self, context):
        if self.request.user.is_authenticated and self.request.user.user_profile.active and self.request.user.user_profile.email_confirmed:
            return redirect('accounts:dashboard_view')
        return super().render_to_response(context)
class RegisterView(View):
    def get(self, request, *args, **kwrags):
        signup_form = SignUpForm()
        context = {
            'signup_form': signup_form,
            'title': 'Register'
        }
        return render(request, 'accounts/register.html', context)
    def post(self, request, *args, **kwrags):
        signup_form = SignUpForm(request.POST)
        if signup_form.is_valid():
            user = signup_form.save()
            user.refresh_from_db()
            user.user_profile.phone_number = signup_form.cleaned_data.get(
                'phone_number')
            user.save()
            user.user_profile.save()
            current_site = get_current_site(request)
            subject = 'Activate Your Account'
            message = render_to_string('accounts/acc_active_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
            })
            user.email_user(subject, message)
            messages.success(
                request, ('Registration Completed.Please Confirm Your Email Address'))
            return redirect('accounts:login')
        else:
            context = {
                'signup_form': signup_form,
                'title': 'Register'
            }
            return render(request, 'accounts/register.html', context)
def activate(request, uidb64, token):
    try:
        uid = force_bytes(urlsafe_base64_decode(uidb64))
        user = get_user_model().objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and account_activation_token.check_token(user, token):
        user.user_profile.email_confirmed = True
        user.user_profile.save()
        messages.success(
            request, ('Thank You For Confirm The Email.Your Account Will Be Activated Soon'))
        return redirect('accounts:login')
    else:
        messages.success(request, ('Activation link is invalid!'))
        return redirect('accounts:login')
class MyProfileView(AictiveUserRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user_form = UserForm(instance=request.user)
        profile_form = ProfileForm(instance=request.user.user_profile)
        context = {
            'user_form': user_form,
            'profile_form': profile_form,
            'title': 'My Profile'
        }
        return render(request, 'accounts/my_profile.html', context)
    def post(self, request, *args, **kwargs):
        user_form = UserForm(request.POST,
                             instance=request.user)
        profile_form = ProfileForm(
            request.POST, request.FILES, instance=request.user.user_profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('accounts:my_profile')
        else:
            context = {
                'user_form': user_form,
                'profile_form': profile_form,
                'title': 'My Profile'
            }
            return render(request, 'accounts/my_profile.html', context)
class ChangePasswordView(AictiveUserRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        password_changeform = PasswordChangeForm(request.user)
        context = {
            'chanage_password_form': password_changeform,
            'title': 'Change Password'
        }
        return render(request, 'accounts/change_password.html', context)
    def post(self, request, *args, **kwargs):
        chanage_password_form = PasswordChangeForm(
            data=request.POST, user=request.user)
        context = {
            'chanage_password_form': chanage_password_form,
            'title': 'Change Password'
        }
        if chanage_password_form.is_valid():
            chanage_password_form.save()
            update_session_auth_hash(request, chanage_password_form.user)
            messages.success(request, 'You have Changed Your Password...')
            return redirect('accounts:change_password')
        else:
            return render(request, 'accounts/change_password.html', context)
class DashboardView(View):
    def get(self, request, *args, **kwrags):
        """
        Redirects users based on whether they are in the admins group
        """
        if not request.user.is_superuser:
            return redirect("accounts:user_dashboard")
        elif request.user.is_superuser:
            return redirect('admin:login')
        else:
            return redirect("accounts:login")
class UserDashboardView(AictiveUserRequiredMixin, View):
    def get(self, request, *args, **kwrags):
        user_obj = request.user
        user_profile = user_obj.user_profile

        total_booking = Booking.objects.select_related(
            'connection', 'reffiling').filter(user=self.request.user).count()

        confirmed_booking = Booking.objects.select_related(
            'connection', 'reffiling').filter(user=self.request.user, status='1').count()

        on_the_way_booking = Booking.objects.select_related(
            'connection', 'reffiling').filter(user=self.request.user, status='2').count()

        completed_booking = Booking.objects.select_related(
            'connection', 'reffiling').filter(user=self.request.user, status='3').count()

        instructions = Instruction.objects.prefetch_related(
            'instructions').all()

        context = {
            'title': 'User Dashboard',
            'user_obj': user_obj,
            'user_profile': user_profile,
            'total_booking': total_booking,
            'confirmed_booking': confirmed_booking,
            'on_the_way_booking': on_the_way_booking,
            'completed_booking': completed_booking,
            'instructions': instructions
        }

        return render(request, 'accounts/user_dashboard.html', context)
class PaymentDetailsView(AictiveUserRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user_all_payment = PaymentCreditCard.objects.filter(
            owner=request.user)
        context = {
            'title': 'Payment Details',
            'user_all_payment': user_all_payment
        }
        return render(request, 'payment/payment_details.html', context)
class AddCreditCardView(SuccessMessageMixin, AictiveUserRequiredMixin, generic.CreateView):
    model = PaymentCreditCard
    form_class = PaymentCreditCardForm
    template_name = 'payment/add_credit_card.html'
    success_message = 'Credit Card Added SuccessFully'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Credit Card'
        return context
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super(AddCreditCardView, self).form_valid(form)
class EditCreditCardView(SuccessMessageMixin, AictiveUserRequiredMixin, generic.edit.UpdateView):
    model = PaymentCreditCard
    context_object_name = 'user_credit_card'
    form_class = PaymentCreditCardForm
    template_name = 'payment/edit_credit_card.html'
    success_message = 'Credit Card Edit SuccessFully'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Credit Card'
        return context
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)
class DeleteCreditCardView(SuccessMessageMixin, AictiveUserRequiredMixin, generic.edit.DeleteView):
    model = PaymentCreditCard
    template_name = 'payment/delete_credit_card.html'
    success_message = 'Credit Card Deleted SuccessFully'
    success_url = reverse_lazy('accounts:payment_details')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Delete Credit Card'
        return context
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super(DeleteCreditCardView, self).delete(request, *args, **kwargs)
    




    from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gas', '0017_auto_20200922_2112'),
    ]

    operations = [
        migrations.AddField(
            model_name='gasreffiling',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='gas'),
        ),
    ]




    from django.db import models
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
import random
from django.utils.crypto import get_random_string
import uuid
# Create your models here.
User = get_user_model()
class Staff(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='staff')
    mobile = models.CharField(max_length=20)
    address = models.CharField(max_length=255)
    class Meta:
        verbose_name = 'Staff'
        verbose_name_plural = '1. Delivery Staff'
    def __str__(self):
        return self.user.username
def create_new_ref_number():
    return uuid.uuid4().hex[:11].upper()
class Connection(models.Model):
    STATUS_CHOICES = (
        ('1', 'Approved'),
        ('2', 'On Hold'),
        ('3', 'Rejected'),
    )
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='user_connection')
    connection_number = models.CharField(
        max_length=10,
        blank=True,
        editable=False,
        unique=True,
        default=uuid.uuid4
    )
    name = models.CharField(max_length=200)
    email = models.EmailField(max_length=200)
    mobile = models.CharField(max_length=20)
    gender = models.CharField(max_length=20)
    address = models.CharField(max_length=255)
    id_proof = models.ImageField(upload_to='connection')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='2')
    class Meta:
        verbose_name = 'Connection'
        verbose_name_plural = '2. New Connection'
    def get_absolute_url(self):
        return reverse('gas:view_connection', kwargs={'pk': self.pk})
    def __str__(self):
        return self.connection_number
class GasReffiling(models.Model):
    reffiling_size = models.CharField(max_length=50)
    price = models.FloatField()
    image = models.ImageField(upload_to='gas', null=True, blank=True)

    class Meta:
        verbose_name = 'GasReffiling'
        verbose_name_plural = '3.Gas Reffiling'
    def __str__(self):
        return f"{self.reffiling_size} -->> {self.price}TK"
class Booking(models.Model):
    BOOKING_STATUS = (
        ('1', 'Confirmed'),
        ('2', 'On The Way'),
        ('3', 'Delivered'),
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='user_bookings')
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE)
    reffiling = models.ForeignKey(GasReffiling, on_delete=models.CASCADE)
    booking_number = models.CharField(
        max_length=10,
        blank=True,
        editable=False,
        unique=True,
        default=uuid.uuid4
    )
    status = models.CharField(
        max_length=10, choices=BOOKING_STATUS, null=True, blank=True)
    staff = models.ForeignKey(
        Staff, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField(auto_now_add=True, auto_now=False)
    class Meta:
        verbose_name = 'Booking'
        verbose_name_plural = '4.Booking'
    def __str__(self):
        return self.booking_number
    



    from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
import datetime
from django.utils.timezone import now, localtime
from accounts.mixins import AictiveUserRequiredMixin, UserHasPaymentSystem, UserHassApprovedConnection
from django.contrib.messages.views import SuccessMessageMixin

from gas.models import Connection, Booking
from gas.models import Connection, Booking, GasReffiling
from gas.forms import ConnectionForm, BookingForm
from django.views import View, generic
# Create your views here.


class HomeView(generic.TemplateView):
class HomeView(generic.ListView):
    model = GasReffiling
    context_object_name = 'cylinder_list'
    paginate_by = 10
    template_name = 'landing/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Home'
        context['title'] = 'Cylinder List'
        return context


class NewConnectionView(SuccessMessageMixin, AictiveUserRequiredMixin, generic.edit.CreateView):
    model = Connection
    template_name = 'connection/new_connection.html'
    form_class = ConnectionForm
    success_message = 'New Connection Created Successfully'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'New Connection'
        return context
    def get_form_kwargs(self, **kwargs):
        form_kwargs = super().get_form_kwargs(**kwargs)
        form_kwargs["user"] = self.request.user
        return form_kwargs
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(NewConnectionView, self).form_valid(form)
class DetailConnectionView(SuccessMessageMixin, AictiveUserRequiredMixin, generic.detail.DetailView):
    model = Connection
    context_object_name = 'connection'
    template_name = 'connection/view_connection.html'
    # def get_queryset(self):
    #     qs = super().get_queryset()
    #     return qs.filter(status='1')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = self.object.name
        return context
class UpdateConnectionView(SuccessMessageMixin, AictiveUserRequiredMixin, generic.edit.UpdateView):
    model = Connection
    context_object_name = 'connection'
    template_name = 'connection/update_connection.html'
    form_class = ConnectionForm
    success_message = 'Connection Updated Successfully'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Connection'
        return context
    def get_form_kwargs(self, **kwargs):
        form_kwargs = super().get_form_kwargs(**kwargs)
        form_kwargs["user"] = self.request.user
        form_kwargs["update"] = True
        return form_kwargs
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(UpdateConnectionView, self).form_valid(form)
class ApprovedConnectionView(AictiveUserRequiredMixin, generic.ListView):
    model = Connection
    context_object_name = 'connection_list'
    template_name = 'connection/approved_connection.html'
    def get_queryset(self):
        qs = Connection.objects.select_related('user').filter(status='1').only(
            'connection_number', 'name', 'email', 'mobile', 'address', 'user__username')
        return qs
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Approved Connection'
        return context
class BookingCylinderView(UserHasPaymentSystem, UserHassApprovedConnection, SuccessMessageMixin, AictiveUserRequiredMixin, generic.CreateView):
    model = Booking
    template_name = 'booking/booking_cylinder.html'
    form_class = BookingForm
    success_message = 'Cylinder Booked Successfully'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Booking Cylinder'
        context['connection_id'] = self.kwargs.get('connection_id')
        return context
    def get_form_kwargs(self, **kwargs):
        form_kwargs = super().get_form_kwargs(**kwargs)
        form_kwargs["user"] = self.request.user
        return form_kwargs
    def get_success_url(self):
        return reverse_lazy('gas:booking_list')
    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.connection = get_object_or_404(
            Connection, id=self.kwargs.get('connection_id'))
        return super(BookingCylinderView, self).form_valid(form)
class BookingListView(AictiveUserRequiredMixin, generic.ListView):
    model = Booking
    context_object_name = 'booking_list'
    template_name = 'booking/booking_list.html'
    form_class = BookingForm
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Booking List'
        return context
    def get_queryset(self):
        qs = super().get_queryset()

        if self.request.GET.get('type') == 'confirm':
            return qs.select_related('connection', 'booking').filter(user=self.request.user, status='1')
            return qs.select_related('connection', 'reffiling').filter(user=self.request.user, status='1')
        elif self.request.GET.get('type') == 'on_the_way':

            return qs.select_related('connection', 'booking').filter(user=self.request.user, status='2')
            return qs.select_related('connection', 'reffiling').filter(user=self.request.user, status='2')
        elif self.request.GET.get('type') == 'completed':

            return qs.select_related('connection', 'booking').filter(user=self.request.user, status='3')
            return qs.select_related('connection', 'reffiling').filter(user=self.request.user, status='3')

        return qs.select_related('connection', 'booking').filter(user=self.request.user)
        return qs.select_related('connection', 'reffiling').filter(user=self.request.user)


class BookingDetailView(AictiveUserRequiredMixin, generic.DetailView):
    model = Booking
    context_object_name = 'booking'
    template_name = 'booking/booking_detail.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Booking Detail'
        return context
    




from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from gas.views import HomeView
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('gas/', include('gas.urls', namespace='gas')),
    path('settings/', include('settings.urls', namespace='settings')),
    path('', HomeView.as_view(), name="home"),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.FORCE_STATIC_FILE_SERVING and not settings.DEBUG:
    settings.DEBUG = True
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    settings.DEBUG = False





    from django.contrib import admin
from .models import ApplicationInstruction, ApplicationInstructionList, SiteInfo, SiteFaq
from .models import Instruction, InstructionList, SiteInfo, SiteFaq
# Register your models here.


class ApplicationInstructionListInline(admin.StackedInline):
    model = ApplicationInstructionList
class InstructionListInline(admin.StackedInline):
    model = InstructionList
    extra = 0


class ApplicationInstructionAdmin(admin.ModelAdmin):
class InstructionAdmin(admin.ModelAdmin):
    list_display = ['title']
    search_fields = ('title',)
    list_per_page = 20
    inlines = [
        ApplicationInstructionListInline
        InstructionListInline
    ]


admin.site.register(ApplicationInstruction, ApplicationInstructionAdmin)
admin.site.register(Instruction, InstructionAdmin)


class SiteInfoAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'site_phone', 'site_email']
    def has_add_permission(self, request):
        return False if self.model.objects.count() > 0 else True
admin.site.register(SiteInfo, SiteInfoAdmin)
class SiteFaqAdmin(admin.ModelAdmin):
    list_display = ['question', 'answer']
    search_fields = ['question', 'answer']
    list_per_page = 20
admin.site.register(SiteFaq, SiteFaqAdmin)







@@ -1,12 +1,13 @@
# Generated by Django 3.1 on 2020-09-22 18:22
from django.db import migrations, models
import django.db.models.deletion
class Migration(migrations.Migration):

    initial = True
    atomic = False

    dependencies = [
    ]
    operations = [
        migrations.CreateModel(
            name='ApplicationInstruction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
            ],
            options={
                'verbose_name': 'Application Instruction',
                'verbose_name_plural': '2.Application Instruction',
            },
        ),
        migrations.CreateModel(
            name='SiteFaq',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True, serialize=False, verbose_name='ID')),
                ('question', models.CharField(max_length=255)),
                ('answer', models.CharField(max_length=255)),
            ],
            options={
                'verbose_name': 'FAQ',
                'verbose_name_plural': '4.FAQ',
            },
        ),
        migrations.CreateModel(
            name='SiteInfo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True, serialize=False, verbose_name='ID')),
                ('site_name', models.CharField(max_length=255)),
                ('site_phone', models.CharField(max_length=20)),
                ('site_email', models.EmailField(max_length=254)),
            ],
            options={
                'verbose_name': 'SiteInfo',
                'verbose_name_plural': '1.SiteInfo',
            },
        ),
        migrations.CreateModel(
            name='ApplicationInstructionList',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('instruction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instructions', to='settings.applicationinstruction')),
                ('instruction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                  related_name='instructions', to='settings.applicationinstruction')),
            ],
            options={
                'verbose_name': 'Instruction',
                'verbose_name_plural': '3. Instruction',
            },
        ),
    ]







    from django.db import migrations


class Migration(migrations.Migration):

    atomic = False
    dependencies = [
        ('settings', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ApplicationInstruction',
            new_name='Instruction',
        ),
        migrations.RenameModel(
            old_name='ApplicationInstructionList',
            new_name='InstructionList',
        ),
        migrations.AlterModelOptions(
            name='instruction',
            options={'verbose_name': 'Instruction',
                     'verbose_name_plural': '2.Instruction'},
        ),
    ]






    from django.db import models
# Create your models here.
class SiteInfo(models.Model):
    site_name = models.CharField(max_length=255)
    site_phone = models.CharField(max_length=20)
    site_email = models.EmailField()
    class Meta:
        verbose_name = 'SiteInfo'
        verbose_name_plural = '1.SiteInfo'
    def __str__(self):
        return self.site_name


class ApplicationInstruction(models.Model):
class Instruction(models.Model):
    title = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'Application Instruction'
        verbose_name_plural = '2.Application Instruction'
        verbose_name = 'Instruction'
        verbose_name_plural = '2.Instruction'

    def __str__(self):
        return self.title


class ApplicationInstructionList(models.Model):
class InstructionList(models.Model):
    instruction = models.ForeignKey(
        ApplicationInstruction, on_delete=models.CASCADE, related_name='instructions')
        Instruction, on_delete=models.CASCADE, related_name='instructions')
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'Instruction'
        verbose_name_plural = '3. Instruction'
    def __str__(self):
        return self.name
class SiteFaq(models.Model):
    question = models.CharField(max_length=255)
    answer = models.CharField(max_length=255)
    class Meta:
        verbose_name = 'FAQ'
        verbose_name_plural = '4.FAQ'
    def __str__(self):
        return self.question
    




    from django.urls import path
from . import views


app_name = "settings"

urlpatterns = [
    path('faq/', views.SiteFaqView.as_view(),
         name="site_faq"),




         from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from settings.models import SiteFaq
from django.views import View, generic

# Create your views here.


class SiteFaqView(generic.ListView):
    model = SiteFaq
    context_object_name = 'faq_list'
    template_name = 'landing/site_faq.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Frequently Asked Questions'
        return context