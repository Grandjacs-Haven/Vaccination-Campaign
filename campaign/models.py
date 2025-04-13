from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

# Custom User Model
class User(AbstractUser):
    ROLE_CHOICES = (
        ('national', 'National User'),
        ('regional', 'Regional User'),
        ('place', 'Place User'),  # New role added
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    region = models.ForeignKey('Region', on_delete=models.SET_NULL, null=True, blank=True)
    place = models.ForeignKey('Place', on_delete=models.SET_NULL, null=True, blank=True)  # New field for place users
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.username

# Campaign Model
class Campaign(models.Model):
    name = models.CharField(max_length=255)
    sia_start_date = models.DateField()
    number_of_districts = models.IntegerField()
    type_of_vaccine = models.CharField(max_length=255)
    round_number = models.CharField(max_length=50)
    is_active = models.BooleanField(default=False)
    places = models.ManyToManyField('Place', related_name='campaigns')  # New field for related places
    country = models.CharField(max_length=255)  # New field for country

    def __str__(self):
        return self.name

# Region Model
class Region(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

# Place Model
class Place(models.Model):
    name = models.CharField(max_length=255)
    region = models.ForeignKey(Region, related_name='places', on_delete=models.CASCADE)

    def __str__(self):
        return self.name

# Thematic Area Model
class ThematicArea(models.Model):
    LEVEL_CHOICES = (
        ('national', 'National'),
        ('regional', 'Regional'),
    )
    name = models.CharField(max_length=255)
    level = models.CharField(max_length=50, choices=[('national', 'National'), ('regional', 'Regional')])
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='thematic_areas')
    comments = models.TextField(blank=True, null=True)
    last_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

# Activity Model
class Activity(models.Model):
    name = models.CharField(max_length=255)
    thematic_area = models.ForeignKey(ThematicArea, on_delete=models.CASCADE, related_name='activities')
    timeline_before_sia = models.CharField(max_length=50, choices=[
        ('1 week', '1 week'),
        ('2 weeks', '2 weeks'),
        ('4 weeks', '4 weeks'),
        ('8 weeks', '8 weeks'),
    ], blank=True, null=True)
    comments = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

# Implementation Status Model
class ImplementationStatus(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    scale = models.IntegerField(choices=[
        (0, '0'),
        (5, '5'),
        (10, '10'),
    ], default=0)
    comments = models.TextField(blank=True, null=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('activity', 'place')

    def __str__(self):
        return f"{self.activity.name} - {self.place.name}"
    
class NationalImplementationStatus(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    scale = models.IntegerField(choices=[(0, '0'), (5, '5'), (10, '10')], default=0)
    comments = models.TextField(blank=True, null=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.activity.name} - National Implementation"
    
class HistoricalScale(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    scale = models.IntegerField()  # Expected values: 0, 5, or 10
    date_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.place} - {self.activity} - {self.scale} at {self.date_updated}"