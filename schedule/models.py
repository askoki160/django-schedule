from django.db import models
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q

import datetime


class Group(models.Model):
    group_name = models.CharField(max_length=30)
    supervisor = models.ForeignKey(User, related_name='+',)

    def __init__(self, *args, **kwargs):
        super(Group, self).__init__(*args, **kwargs)
        if hasattr(self, 'supervisor'):
            self.old_supervisor = self.supervisor

    def get_members(self):
        return self.user_profile_set.all()

    def __unicode__(self):
        return self.group_name


class Day_shift(models.Model):
    time_from = models.TimeField(null=True, blank=True)
    time_until = models.TimeField(null=True, blank=True)

    def __unicode__(self):
        return 'Day_shift ' + str(self.time_from) + '-' + str(self.time_until)


class Week_shift(models.Model):
    name = models.CharField(max_length=30)
    monday = models.ForeignKey(Day_shift, null=True, blank=True, related_name='+')
    tuesday = models.ForeignKey(Day_shift, null=True, blank=True, related_name='+')
    wednesday = models.ForeignKey(Day_shift, null=True, blank=True, related_name='+')
    thursday = models.ForeignKey(Day_shift, null=True, blank=True, related_name='+')
    friday = models.ForeignKey(Day_shift, null=True, blank=True, related_name='+')
    saturday = models.ForeignKey(Day_shift, null=True, blank=True, related_name='+')
    sunday = models.ForeignKey(Day_shift, null=True, blank=True, related_name='+')
    week_group = models.ForeignKey(Group)

    def save(self, *args, **kwargs):
        if self.monday == None:
            self.monday = Day_shift.objects.create()
        if self.tuesday == None:
            self.tuesday = Day_shift.objects.create()
        if self.wednesday == None:
            self.wednesday = Day_shift.objects.create()
        if self.thursday == None:
            self.thursday = Day_shift.objects.create()
        if self.friday == None:
            self.friday = Day_shift.objects.create()
        if self.saturday == None:
            self.saturday = Day_shift.objects.create()
        if self.sunday == None:
            self.sunday = Day_shift.objects.create()

        super(Week_shift, self).save(*args, **kwargs)

    def get_all_days(self):
        return [self.monday, self.tuesday, self.wednesday, self.thursday, self.friday, self.saturday, self.sunday]

    def get_day(self, x):
        return {
            0: self.monday,
            1: self.tuesday,
            2: self.wednesday,
            3: self.thursday,
            4: self.friday,
            5: self.saturday,
            6: self.sunday,
        }.get(x, 6)

    def change_day(self, x, val):
        if x == 0:
            self.monday = val
        elif x == 1:
            self.tuesday = val
        elif x == 2:
            self.wednesday = val
        elif x == 3:
            self.thursday = val
        elif x == 4:
            self.friday = val
        elif x == 5:
            self.saturday = val
        elif x == 6:
            self.sunday = val

    def __unicode__(self):
        return self.name


class User_profile(models.Model):
    GENDER_CHOICES = (
        ('M', _('Male')),
        ('F', _('Female')),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_groups = models.ManyToManyField(Group)
    user_shift = models.ForeignKey(Week_shift, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True, blank=True)
    date_of_employment = models.DateField(null=True, blank=True)
    default_wage = models.DecimalField(decimal_places=2, max_digits=5, default=0, blank=True)

    def __init__(self, *args, **kwargs):
        super(User_profile, self).__init__(*args, **kwargs)
        if hasattr(self, 'user_shift'):
            self.old_shift = self.user_shift

    def generate_schedule(self):
        today = datetime.datetime.today()
        numdays = 60
        for x in range(0, numdays):
            date = today + datetime.timedelta(days=x)
            try:
                Schedule.objects.get(date=date, user=self, schedule=None)
            except:
                Schedule.objects.create(date=date, user=self, schedule=None)

    def get_current_working_hours(self):
        month_current = datetime.date.today()
        month_1st = month_current.replace(day=1)
        all_schedules = Schedule.objects.filter(date__range=[month_1st, month_current], user=self)
        time_sum = 0
        for schedule in all_schedules.all():
            # If schedule is not None 
            if schedule.time_until and schedule.time_from:
                time_sum += schedule.time_until.hour - schedule.time_from.hour
        return time_sum

    def calculate_current_paycheck(self):
        return self.get_current_working_hours() * self.default_wage

    def __unicode__(self):
        return self.user.first_name + ' ' + self.user.last_name


@receiver(post_save, sender=Group)
def update_supervisor(sender, instance, created, **kwargs):
    # if instance is created and supervisor is changed
    if instance:
        try:
            new_supervisor = User_profile.objects.get(user=instance.supervisor)
        except:
            return
        new_supervisor.user_groups.add(instance)
        new_supervisor.save()

        # If first created old supervisor will be same as new
        if instance.supervisor != instance.old_supervisor:
            try:
                old_supervisor = User_profile.objects.get(
                    user=instance.old_supervisor)
            except:
                return
            old_supervisor.user_groups.remove(instance)
            old_supervisor.save()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        User_profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if instance.user_profile.user_shift:
        instance.user_profile.save()


@receiver(post_save, sender=User_profile)
def generate_user_schedule(sender, instance, created, *args, **kwargs):
    # If User_profile is not created then then dont generate schedule
    # If user_shift is not changed then dont generate schedule
    # If user shift is set to None then dont generate schedule
    if not created and (instance.user_shift != instance.old_shift) and instance.user_shift != None:
        month_current = datetime.date.today()
        schedules_to_remove = Schedule.objects.filter(Q(date__gte=month_current), user=instance)
        for schedule in schedules_to_remove:
            schedule.delete()
        instance.generate_schedule()


class Schedule(models.Model):
    schedule = models.ForeignKey(
        "self",
        related_name='+',
        verbose_name=_('Parent schedule'),
        null=True,
        blank=True
    )
    date = models.DateField()
    time_from = models.TimeField(null=True, blank=True)
    time_until = models.TimeField(null=True, blank=True)
    user = models.ForeignKey(User_profile)

    def save(self, make_instance=False, *args, **kwargs):
        if (self.time_from == None or self.time_until == None) and self.user.user_shift != None:
            temp_shift = self.user.user_shift.get_day(self.date.weekday())

            self.time_from = temp_shift.time_from
            self.time_until = temp_shift.time_until

        if make_instance == True:
            # In case of change - followup
            try:
                new_followup = Schedule.objects.get(pk=self.pk)
                new_followup.pk = None
                new_followup.schedule = self
                new_followup.save()
            except:
                pass
        # Call the "real" save() method.
        super(Schedule, self).save(*args, **kwargs)

    def get_string_from(self):
        if self.time_from:
            return self.date.strftime('%Y-%m-%d') + 'T' + self.time_from.strftime('%H:%M:%S')
        else:
            return None

    def get_string_until(self):
        if self.time_until:
            return self.date.strftime('%Y-%m-%d') + 'T' + self.time_until.strftime('%H:%M:%S')
        else:
            return None

    def __unicode__(self):
        return 'Schedule ' + self.date.strftime('%m/%d/%Y') + ' ' + self.user.user.first_name + ' ' + self.user.user.last_name


class Swap(models.Model):
    schedule_1 = models.ForeignKey(Schedule, related_name='+')
    schedule_2 = models.ForeignKey(Schedule, related_name='+')
    date = models.DateField()
    permanent = models.BooleanField(default=False)
    status = models.BooleanField(default=False)

    def revert(self):
        self.save(make_instance=False)
        self.delete()

    def save(self, make_instance=True, *args, **kwargs):
        if self.status == True:
            # Swap schedules(class) which enables change to be visible in real
            # schedule
            sch_1 = Schedule.objects.get(pk=self.schedule_1.pk)
            sch_2 = Schedule.objects.get(pk=self.schedule_2.pk)

            if self.permanent == True:
                shift_1 = sch_1.user.user_shift
                shift_2 = sch_2.user.user_shift

                day_1 = shift_1.get_day(sch_1.date.weekday())
                day_2 = shift_2.get_day(sch_2.date.weekday())

                shift_1.change_day(sch_1.date.weekday(), day_2)
                shift_1.save()
                shift_2.change_day(sch_2.date.weekday(), day_1)
                shift_2.save()

            sch_1.user, sch_2.user = sch_2.user, sch_1.user
            sch_1.save(make_instance=make_instance)
            sch_2.save(make_instance=make_instance)
        
        # save current state if reverse is used
        if make_instance == False:
            follow_schedule_1 = Schedule.objects.get(schedule=sch_1)
            follow_schedule_2 = Schedule.objects.get(schedule=sch_2)
            follow_schedule_1.delete()
            follow_schedule_2.delete()

        super(Swap, self).save(*args, **kwargs)

    def __unicode__(self):
        return 'Swap ' + self.date.strftime('%m/%d/%Y') + ' ' + str(self.id)
