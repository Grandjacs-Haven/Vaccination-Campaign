from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import cache_control
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from .forms import (
    RegionalUserCreationForm,
    NationalLoginForm,
    RegionalLoginForm,
    ThematicAreaForm,
    ActivityForm,
    ImplementationStatusForm,
    PlaceForm,
    PlaceUserCreationForm,
    PlaceLoginForm,
    NationalUserCreationForm,
)
from .models import (
    User,
    Campaign,
    Region,
    Place,
    ThematicArea,
    Activity,
    ImplementationStatus,
    NationalImplementationStatus,
    HistoricalScale,
)
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from django.http import HttpResponse
import csv
from django.utils import timezone
from django.http import JsonResponse
from collections import defaultdict
import json
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.db.models import Q


from django.template.loader import render_to_string

from weasyprint import HTML, CSS

from .utilities import restrict_access


import matplotlib

import matplotlib.pyplot as plt

import base64
from io import BytesIO


def main_page(request):
    return render(request, "campaign/main_page.html")


def national_login(request):
    if request.method == "POST":
        form = NationalLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            if user.role != "national":
                messages.error(request, "Access restricted to national users.")
                return redirect("national_login")

            return redirect("national_dashboard")
    else:
        form = NationalLoginForm()

    return render(request, "campaign/national_login.html", {"form": form})


def regional_login(request):
    if request.method == "POST":
        form = RegionalLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)

            if user is not None and user.role == "regional":

                region = user.region

                login(request, user)
                return redirect("regional_dashboard")
            else:
                messages.error(
                    request,
                    "Invalid username or password.",
                    extra_tags="regional_login_error",
                )
    else:
        form = RegionalLoginForm()

    return render(request, "campaign/regional_login.html", {"form": form})


def user_logout(request):
    logout(request)
    return redirect("main_page")


@login_required
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
@restrict_access(allowed_roles=["national"])
def national_dashboard(request):

    campaign = Campaign.objects.filter(is_active=True).first()
    current_date = timezone.now().date()

    if campaign:

        days_to_campaign = (campaign.sia_start_date - current_date).days
        weeks_to_campaign = days_to_campaign // 7

        thematic_areas = (
            ThematicArea.objects.filter(campaign=campaign, level="national")
            .order_by("name")
            .prefetch_related("activities")
        )

        national_data = {}
        for thematic_area in thematic_areas:
            activities_data = []
            for activity in thematic_area.activities.all():

                status, created = NationalImplementationStatus.objects.get_or_create(
                    activity=activity, campaign=campaign
                )

                activities_data.append(
                    {
                        "activity": activity,
                        "scale": status.scale,
                        "comments": status.comments,
                        "form": ImplementationStatusForm(
                            instance=status, prefix=f"{activity.id}"
                        ),
                    }
                )

            total_score = sum(item["scale"] for item in activities_data)
            max_total = thematic_area.activities.count() * 10
            total_percentage = (
                round((total_score / max_total) * 100, 2) if max_total > 0 else 0
            )

            national_data[thematic_area] = {
                "activities": activities_data,
                "total_percentage": total_percentage,
                "comments": thematic_area.comments,
            }

        thematic_status = [
            {
                "name": thematic_area.name,
                "percentage": national_data[thematic_area]["total_percentage"],
            }
            for thematic_area in thematic_areas
        ]
        status_of_preparedness = (
            round(
                sum(item["percentage"] for item in thematic_status)
                / len(thematic_status),
                2,
            )
            if thematic_status
            else 0
        )

    else:

        days_to_campaign = None
        weeks_to_campaign = None
        thematic_areas = []
        national_data = {}
        thematic_status = []
        status_of_preparedness = None
        messages.warning(request, "There is currently no active campaign.")

    return render(
        request,
        "campaign/national_dashboard.html",
        {
            "campaign": campaign,
            "campaign_name": campaign.name if campaign else "No Active Campaign",
            "days_to_campaign": days_to_campaign,
            "weeks_to_campaign": weeks_to_campaign,
            "thematic_areas": thematic_areas,
            "national_data": national_data,
            "status_of_preparedness": status_of_preparedness,
            "current_date": current_date,
            "user": request.user,
        },
    )


@login_required
@restrict_access(allowed_roles=["regional","place"])
def regional_dashboard(request):

    campaign = Campaign.objects.filter(is_active=True).first()
    today = timezone.now().date()
    current_date = today

    if not campaign:

        messages.warning(request, "There is currently no active campaign.")
        return render(
            request,
            "campaign/regional_dashboard.html",
            {
                "campaign": None,
                "campaign_name": "No Active Campaign",
                "days_to_campaign": None,
                "weeks_to_campaign": None,
                "thematic_areas": [],
                "regional_data": {},
                "places": [],
                "status_completion": {},
                "preparedness_status": {},
                "current_date": current_date,
                "total_completion_percentages": {},
                "regional_preparedness": 0,
            },
        )

    days_to_campaign = (campaign.sia_start_date - today).days
    weeks_to_campaign = days_to_campaign // 7

    thematic_areas = ThematicArea.objects.filter(
        campaign=campaign, level="regional"
    ).prefetch_related("activities")

    if request.user.role == "regional":
        all_places_in_region = request.user.region.places.all()
        campaign_places = campaign.places.all()
        places = all_places_in_region.filter(
            id__in=campaign_places.values_list("id", flat=True)
        )
    elif request.user.role == "place":
        if campaign.places.filter(id=request.user.place.id).exists():
            places = Place.objects.filter(id=request.user.place.id)
        else:
            places = Place.objects.none()
    else:
        messages.error(request, "You are not authorized to view this dashboard.")
        return redirect("main_page")

    if not places.exists():
        messages.warning(
            request,
            "No places assigned to you are participating in the current campaign.",
        )
        return render(
            request,
            "campaign/regional_dashboard.html",
            {
                "campaign": campaign,
                "campaign_name": campaign.name,
                "days_to_campaign": days_to_campaign,
                "weeks_to_campaign": weeks_to_campaign,
                "thematic_areas": thematic_areas,
                "regional_data": {},
                "places": [],
                "status_completion": {},
                "preparedness_status": {},
                "current_date": current_date,
                "total_completion_percentages": {},
                "regional_preparedness": 0,
            },
        )

    regional_data = {}
    status_completion = {}
    preparedness_status = {}
    total_completion_percentages = {}

    for thematic_area in thematic_areas:
        activities_data = []
        for activity in thematic_area.activities.all():
            place_data = []
            for place in places:
                status, created = ImplementationStatus.objects.get_or_create(
                    activity=activity, place=place
                )
                place_data.append(
                    {
                        "place": place,
                        "scale": status.scale,
                        "comments": status.comments,
                        "form": ImplementationStatusForm(
                            instance=status, prefix=f"{activity.id}_{place.id}"
                        ),
                    }
                )

            total_possible = len(places) * 10
            total_score = sum(item["scale"] for item in place_data)
            total_percentage = (
                (total_score / total_possible) * 100 if total_possible > 0 else 0
            )

            activities_data.append(
                {
                    "activity": activity,
                    "place_data": place_data,
                    "regional_score": (
                        total_score if request.user.role == "regional" else None
                    ),
                    "total_percentage": round(total_percentage, 2),
                    "timeline": weeks_to_campaign,
                    "comments": activity.comments,
                }
            )

        regional_data[thematic_area] = activities_data

        total_score_all_places = sum(
            item["regional_score"]
            for item in activities_data
            if item["regional_score"] is not None
        )
        total_possible_all_places = len(places) * thematic_area.activities.count() * 10
        total_completion_percentage = (
            (total_score_all_places / total_possible_all_places) * 100
            if total_possible_all_places > 0
            else 0
        )

        region_or_place_key = (
            request.user.region.name
            if request.user.role == "regional"
            else request.user.place.name
        )
        total_completion_percentages.setdefault(region_or_place_key, {})[
            thematic_area.name
        ] = round(total_completion_percentage, 2)

        for place in places:
            total_score = (
                ImplementationStatus.objects.filter(
                    activity__thematic_area=thematic_area, place=place
                ).aggregate(total=Sum("scale"))["total"]
                or 0
            )
            place_percentage = (
                (total_score / (thematic_area.activities.count() * 10)) * 100
                if thematic_area.activities.count() > 0
                else 0
            )
            status_completion.setdefault(thematic_area.name, {})[place.name] = round(
                place_percentage, 2
            )

    for place in places:
        place_total_percentage = sum(
            status_completion.get(thematic_area.name, {}).get(place.name, 0)
            for thematic_area in thematic_areas
        )
        preparedness_status[place.name] = (
            round(place_total_percentage / len(thematic_areas), 2)
            if thematic_areas
            else 0
        )

    regional_preparedness = (
        sum(preparedness_status.values()) / len(preparedness_status)
        if preparedness_status
        else 0
    )

    return render(
        request,
        "campaign/regional_dashboard.html",
        {
            "campaign": campaign,
            "campaign_name": campaign.name if campaign else "No Active Campaign",
            "days_to_campaign": days_to_campaign,
            "weeks_to_campaign": weeks_to_campaign,
            "thematic_areas": thematic_areas,
            "regional_data": regional_data,
            "places": places,
            "status_completion": status_completion,
            "preparedness_status": preparedness_status,
            "current_date": current_date,
            "total_completion_percentages": total_completion_percentages,
            "regional_preparedness": round(regional_preparedness, 2),
        },
    )


@login_required
def update_implementation_status(request):
    if request.method == "POST":
        activity_id = request.POST.get("activity_id")
        place_id = request.POST.get("place_id")
        scale = request.POST.get("scale")
        comments = request.POST.get("comments", "")

        activity = get_object_or_404(Activity, id=activity_id)
        place = get_object_or_404(Place, id=place_id)
        campaign = Campaign.objects.filter(
            is_active=True
        ).first() 

        allowed_scales = ["0", "5", "10"]
        if scale not in allowed_scales:
            return JsonResponse(
                {"error": "Invalid scale value. Allowed values are 0, 5, or 10."},
                status=400,
            )

        scale = int(scale)

        if request.user.role == "regional" and place.region == request.user.region:
            pass
        elif request.user.role == "place" and place == request.user.place:
            pass
        else:
            return JsonResponse({"error": "Unauthorized"}, status=403)

        status, created = ImplementationStatus.objects.get_or_create(
            activity=activity, place=place
        )
        status.scale = scale
        status.comments = comments
        status.save()

        HistoricalScale.objects.create(
            place=place,
            activity=activity,
            campaign=campaign,
            scale=scale,
            date_updated=timezone.now(),
        )

        return JsonResponse(
            {"success": True, "message": "Status updated successfully."}
        )

    return JsonResponse({"error": "Invalid request method. Use POST."}, status=400)


@login_required
@restrict_access(allowed_roles=["national"])
def manage_thematic_areas(request):
    if request.user.role != "national":
        return redirect("main_page")

    campaign = Campaign.objects.filter(is_active=True).first()
    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return redirect("national_dashboard")

    form = ThematicAreaForm()

    if request.method == "POST":
        if "create_thematic_area" in request.POST:
            form = ThematicAreaForm(request.POST)
            if form.is_valid():
                thematic_area = form.save(commit=False)
                thematic_area.campaign = campaign
                thematic_area.save()
                messages.success(request, "Thematic area created successfully.")
                return redirect("manage_thematic_areas")
        elif "delete_thematic_area_id" in request.POST:
            thematic_area_id = request.POST.get("delete_thematic_area_id")
            thematic_area = get_object_or_404(
                ThematicArea, id=thematic_area_id, campaign=campaign
            )
            thematic_area.delete()
            messages.success(request, "Thematic area deleted successfully.")
            return redirect("manage_thematic_areas")

    level_filter = request.GET.get("level")
    thematic_area_filter = request.GET.get("thematic_area")

    thematic_areas = ThematicArea.objects.filter(campaign=campaign).order_by(
        "-last_modified"
    )

    if level_filter:
        thematic_areas = thematic_areas.filter(level=level_filter)
    if thematic_area_filter:
        thematic_areas = thematic_areas.filter(name__icontains=thematic_area_filter)

    return render(
        request,
        "campaign/manage_thematic_areas.html",
        {
            "form": form,
            "thematic_areas": thematic_areas,
            "level_filter": level_filter,
            "thematic_area_filter": thematic_area_filter,
            "campaign": campaign,
        },
    )


@login_required
@restrict_access(allowed_roles=["national"])
def add_activity(request, thematic_area_id):
    if request.user.role != "national":
        return redirect("main_page")

    thematic_area = get_object_or_404(ThematicArea, id=thematic_area_id)
    if request.method == "POST":
        form = ActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.thematic_area = thematic_area
            activity.save()

            thematic_area.last_modified = timezone.now()
            thematic_area.save()

            messages.success(request, "Activity added successfully.")
            return redirect("manage_thematic_areas")
    else:
        form = ActivityForm()

    return render(
        request,
        "campaign/add_activity.html",
        {
            "form": form,
            "thematic_area": thematic_area,
        },
    )


@login_required
@restrict_access(allowed_roles=["national"])
def manage_regions(request):
    if request.user.role != "national":
        return redirect("main_page")

    search_query = request.GET.get("search", "")

    if search_query:
        regions = (
            Region.objects.prefetch_related("places", "user_set")
            .filter(Q(name__icontains=search_query))
            .order_by("name")
        )
    else:
        regions = (
            Region.objects.prefetch_related("places", "user_set").all().order_by("name")
        )

    if request.method == "POST":
        if "create_region" in request.POST:
            name = request.POST.get("name")
            if name:
                Region.objects.create(name=name)
                messages.success(request, "Region created successfully.")
                return redirect("manage_regions")

        if "delete_region" in request.POST:
            region_id = request.POST.get("region_id")
            try:
                region = get_object_or_404(Region, id=region_id)
                region.delete()
                messages.success(request, "Region deleted successfully.")
            except Region.DoesNotExist:
                messages.error(request, "Region not found.")
            return redirect("manage_regions")

        if "delete_user" in request.POST:
            user_id = request.POST.get("user_id")
            try:
                user = get_object_or_404(User, id=user_id)
                user.delete()
                messages.success(request, "User deleted successfully.")
            except User.DoesNotExist:
                messages.error(request, "User not found.")
            return redirect("manage_regions")

    return render(
        request,
        "campaign/manage_regions.html",
        {
            "regions": regions,
            "search_query": search_query,
        },
    )


from django.contrib import messages


@login_required
@restrict_access(allowed_roles=["national"])
def assign_regional_user(request, region_id):
    if request.user.role != "national":
        return redirect("main_page")

    region = get_object_or_404(Region, id=region_id)
    created_user = None

    if request.method == "POST":
        form = RegionalUserCreationForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.role = "regional"
            user.region = region
            raw_password = form.cleaned_data.get("password1")
            user.set_password(raw_password)
            user.save()

            created_user = {"username": user.username, "password": raw_password}
            messages.success(request, "Regional user assigned successfully.")
            return render(
                request,
                "campaign/assign_regional_user.html",
                {
                    "form": RegionalUserCreationForm(),
                    "region": region,
                    "created_user": created_user,
                },
            )

    else:
        form = RegionalUserCreationForm()

    return render(
        request, "campaign/assign_regional_user.html", {"form": form, "region": region}
    )


@login_required
@restrict_access(allowed_roles=["national"])
def assign_place_user(request, place_id):
    if request.user.role != "national":
        return redirect("main_page")

    place = get_object_or_404(Place, id=place_id)
    region = place.region
    created_user = None

    if request.method == "POST":
        form = PlaceUserCreationForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.role = "place"
            user.place = place
            user.region = region
            user.save()

            created_user = {
                "username": user.username,
                "password": form.cleaned_data.get("password1"),
            }

            return render(
                request,
                "campaign/assign_place_user.html",
                {
                    "form": PlaceUserCreationForm(),
                    "place": place,
                    "created_user": created_user,
                },
            )
        else:

            print("Form is invalid.")
            print("Form errors:", form.errors)
            for field, errors in form.errors.items():
                print(f"Error in field '{field}': {errors}")

    else:
        form = PlaceUserCreationForm()

    return render(
        request,
        "campaign/assign_place_user.html",
        {
            "form": form,
            "place": place,
        },
    )


@login_required
@restrict_access(allowed_roles=["national"])
def add_place(request, region_id):
    if request.user.role != "national":
        return redirect("main_page")

    region = get_object_or_404(Region, id=region_id)
    if request.method == "POST":
        form = PlaceForm(request.POST)
        if form.is_valid():
            place = form.save(commit=False)
            place.region = region
            place.save()
            messages.success(request, "Place added successfully.")
            return redirect("manage_regions")
    else:
        form = PlaceForm()

    return render(
        request,
        "campaign/add_place.html",
        {
            "form": form,
            "region": region,
        },
    )


@login_required
@restrict_access(allowed_roles=["national"])
def manage_campaigns(request):
    if request.user.role != "national":
        return redirect("main_page")

    action = request.GET.get("action")

    if action == "clear_session":
        request.session.pop("campaign_form_data", None)
        request.session.pop("selected_places", None)
        return redirect("manage_campaigns")

    selected_places_dict = request.session.get("selected_places", {})
    selected_places_dict = (
        selected_places_dict if isinstance(selected_places_dict, dict) else {}
    )
    selected_places_ids = [
        place for places in selected_places_dict.values() for place in places
    ]
    number_of_districts = len(set(selected_places_ids))
    campaign_form_data = request.session.get("campaign_form_data", {})

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "select_places":

            request.session["campaign_form_data"] = {
                "country": request.POST.get("country"),
                "name": request.POST.get("name"),
                "sia_start_date": request.POST.get("sia_start_date"),
                "type_of_vaccine": request.POST.get("type_of_vaccine"),
                "round_number": request.POST.get("round_number"),
                "is_active": "is_active" in request.POST,
            }
            return HttpResponseRedirect(
                f"{reverse('select_campaign_places')}?from=create"
            )

        elif action == "create_campaign":

            name = request.POST.get("name")
            sia_start_date = request.POST.get("sia_start_date")
            type_of_vaccine = request.POST.get("type_of_vaccine")
            round_number = request.POST.get("round_number")
            is_active = "is_active" in request.POST

            campaign = Campaign.objects.create(
                name=name,
                sia_start_date=sia_start_date,
                number_of_districts=number_of_districts,
                type_of_vaccine=type_of_vaccine,
                round_number=round_number,
                is_active=is_active,
            )
            if selected_places_ids:
                places = Place.objects.filter(id__in=selected_places_ids)
                campaign.places.set(places)

            request.session.pop("campaign_form_data", None)
            request.session.pop("selected_places", None)
            messages.success(request, "Campaign created successfully.")
            return redirect("manage_campaigns")

        elif action == "edit_campaign":

            campaign_id = request.POST.get("campaign_id")
            campaign = get_object_or_404(Campaign, id=campaign_id)
            campaign.name = request.POST.get("name")
            campaign.sia_start_date = request.POST.get("sia_start_date")
            campaign.type_of_vaccine = request.POST.get("type_of_vaccine")
            campaign.round_number = request.POST.get("round_number")
            campaign.country = request.POST.get("country")
            campaign.save()
            messages.success(request, "Campaign updated successfully.")
            return redirect("manage_campaigns")

        elif "clear_round_data" in request.POST:

            campaign_id = request.POST.get("clear_round_data")
            campaign = get_object_or_404(Campaign, id=campaign_id)
            ImplementationStatus.objects.filter(
                activity__thematic_area__campaign=campaign
            ).delete()
            NationalImplementationStatus.objects.filter(
                activity__thematic_area__campaign=campaign
            ).delete()
            messages.success(request, "Round data cleared successfully.")
            return redirect("manage_campaigns")

        elif "is_active_campaign" in request.POST:

            active_campaign_id = request.POST.get("is_active_campaign")
            Campaign.objects.update(is_active=False)
            Campaign.objects.filter(id=active_campaign_id).update(is_active=True)
            messages.success(request, "Campaign activated successfully.")

            if "redirect_to_dashboard" in request.GET:
                return redirect("national_dashboard")
            else:
                return redirect("manage_campaigns")

        elif "delete_campaign" in request.POST:

            campaign_id = request.POST.get("delete_campaign")
            campaign = get_object_or_404(Campaign, id=campaign_id)
            campaign.delete()
            messages.success(request, "Campaign deleted successfully.")
            return redirect("manage_campaigns")

    campaigns = Campaign.objects.all()
    active_campaign = campaigns.filter(is_active=True).first()
    active_campaign_name = (
        active_campaign.name if active_campaign else "No Active Campaign"
    )

    if action == "create":
        return render(
            request,
            "campaign/create_campaign.html",
            {
                "campaign_form_data": campaign_form_data,
                "number_of_districts": number_of_districts,
            },
        )

    return render(
        request,
        "campaign/manage_campaigns.html",
        {
            "campaigns": campaigns,
            "active_campaign_name": active_campaign_name,
        },
    )


@login_required
@restrict_access(allowed_roles=["national"])
def select_campaign_places(request):
    if request.user.role != "national":
        return redirect("main_page")

    regions = Region.objects.all()
    selected_region = None
    places = []

    if "selected_places" not in request.session or not isinstance(
        request.session["selected_places"], dict
    ):
        request.session["selected_places"] = {}

    selected_places_dict = request.session["selected_places"]

    if request.method == "GET":
        region_id = request.GET.get("region")
        if region_id:
            try:
                selected_region = Region.objects.get(id=region_id)
                places = Place.objects.filter(region=selected_region)
            except Region.DoesNotExist:

                messages.error(
                    request,
                    "Selected region does not exist.",
                    extra_tags="campaign_selection",
                )
                return redirect("select_campaign_places")

    elif request.method == "POST":
        region_id = request.POST.get("region")
        if not region_id:

            messages.error(
                request, "No region selected.", extra_tags="campaign_selection"
            )
            return redirect("select_campaign_places")

        try:
            selected_region = Region.objects.get(id=region_id)
            places = Place.objects.filter(region=selected_region)
        except Region.DoesNotExist:

            messages.error(
                request,
                "Selected region does not exist.",
                extra_tags="campaign_selection",
            )
            return redirect("select_campaign_places")

        selected_places = request.POST.getlist("places")

        selected_places_dict[str(selected_region.id)] = selected_places
        request.session["selected_places"] = selected_places_dict
        request.session.modified = True

        messages.success(
            request,
            f"Selected Districts for {selected_region.name} have been saved.",
            extra_tags="campaign_selection",
        )

        return redirect("select_campaign_places")

    all_selected_place_ids = []
    if isinstance(selected_places_dict, dict):
        for place_ids in selected_places_dict.values():
            all_selected_place_ids.extend(place_ids)

    selected_places_ids = (
        selected_places_dict.get(str(selected_region.id), []) if selected_region else []
    )

    context = {
        "regions": regions,
        "selected_region": selected_region,
        "places": places,
        "selected_places_ids": selected_places_ids,
        "all_selected_place_ids": all_selected_place_ids,
    }

    return render(request, "campaign/select_campaign_places.html", context)


@login_required
@restrict_access(allowed_roles=["national"])
def regional_preparedness(request):
    if request.user.role != "national":
        return redirect("main_page")

    campaign = Campaign.objects.filter(is_active=True).first()
    days_to_campaign = (
        (campaign.sia_start_date - timezone.now().date()).days if campaign else None
    )
    weeks_to_campaign = days_to_campaign // 7 if days_to_campaign is not None else None

    regions = (
        Region.objects.filter(places__in=campaign.places.all()).distinct()
        if campaign
        else Region.objects.none()
    )

    selected_region_id = request.GET.get("region")
    selected_region = None
    regional_data = {}
    status_completion = {}
    preparedness_status = {}
    total_completion_percentages = {}
    search_term = request.GET.get("search", "").strip()

    if selected_region_id and campaign:

        selected_region = get_object_or_404(Region, id=selected_region_id)
        places = selected_region.places.filter(
            id__in=campaign.places.values_list("id", flat=True)
        )

        thematic_areas = ThematicArea.objects.filter(
            campaign=campaign, level="regional"
        )

        if search_term:
            thematic_areas = thematic_areas.filter(name__icontains=search_term)

        thematic_areas = thematic_areas.prefetch_related("activities")

        total_completion_percentages[selected_region.name] = {}

        for thematic_area in thematic_areas:
            activities_data = []
            for activity in thematic_area.activities.all():
                place_data = []
                for place in places:
                    status = ImplementationStatus.objects.filter(
                        activity=activity, place=place
                    ).first()
                    scale = status.scale if status else 0
                    comments = status.comments if status else "None"
                    place_data.append(
                        {
                            "place": place,
                            "scale": scale,
                            "comments": comments,
                        }
                    )

                total_possible = len(places) * 10
                total_score = sum(item["scale"] for item in place_data)
                total_percentage = (
                    (total_score / total_possible) * 100 if total_possible > 0 else 0
                )
                activities_data.append(
                    {
                        "activity": activity,
                        "place_data": place_data,
                        "regional_score": total_score,
                        "total_percentage": round(total_percentage, 2),
                        "timeline": activity.timeline_before_sia,
                        "comments": activity.comments,
                    }
                )
            regional_data[thematic_area] = activities_data

            total_score_all_places = sum(
                item["regional_score"] for item in activities_data
            )
            total_possible_all_places = (
                len(places) * thematic_area.activities.count() * 10
            )
            total_completion_percentage = (
                (total_score_all_places / total_possible_all_places) * 100
                if total_possible_all_places > 0
                else 0
            )
            total_completion_percentages[selected_region.name][thematic_area.name] = (
                round(total_completion_percentage, 2)
            )

            for place in places:
                total_score = (
                    ImplementationStatus.objects.filter(
                        activity__thematic_area=thematic_area, place=place
                    ).aggregate(total=Sum("scale"))["total"]
                    or 0
                )
                place_percentage = (
                    (total_score / (thematic_area.activities.count() * 10)) * 100
                    if thematic_area.activities.count() > 0
                    else 0
                )
                status_completion.setdefault(thematic_area.name, {})[place.name] = (
                    round(place_percentage, 2)
                )

        for place in places:
            place_total_percentage = sum(
                status_completion.get(thematic_area.name, {}).get(place.name, 0)
                for thematic_area in thematic_areas
            )
            preparedness_status[place.name] = (
                round(place_total_percentage / len(thematic_areas), 2)
                if thematic_areas
                else 0
            )

    current_date = timezone.now().date()
    return render(
        request,
        "campaign/regional_preparedness.html",
        {
            "campaign": campaign,
            "campaign_name": campaign.name if campaign else "No Active Campaign",
            "days_to_campaign": days_to_campaign,
            "weeks_to_campaign": weeks_to_campaign,
            "regions": regions,
            "selected_region": selected_region,
            "regional_data": regional_data,
            "status_completion": status_completion,
            "preparedness_status": preparedness_status,
            "current_date": current_date,
            "total_completion_percentages": total_completion_percentages,
            "places": places if selected_region else [],
            "search_term": search_term,
        },
    )


@login_required
@restrict_access(allowed_roles=["regional"])
def export_csv_regional(request):
    if request.user.role != "regional":
        return redirect("main_page")

    campaign = Campaign.objects.filter(is_active=True).first()
    current_date = timezone.now().date()

    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return redirect("regional_dashboard")

    days_to_campaign = (
        (campaign.sia_start_date - current_date).days if campaign else None
    )
    weeks_to_campaign = (
        f"{days_to_campaign // 7} week(s)" if days_to_campaign is not None else "N/A"
    )

    campaign_places = campaign.places.all()
    region = request.user.region
    places = region.places.filter(id__in=campaign_places.values_list("id", flat=True))

    status_completion = {}
    latest_updates = {}
    thematic_areas = ThematicArea.objects.filter(
        campaign=campaign, level="regional"
    ).prefetch_related("activities")

    for thematic_area in thematic_areas:
        for place in places:

            total_score = (
                ImplementationStatus.objects.filter(
                    activity__thematic_area=thematic_area, place=place
                ).aggregate(total=Sum("scale"))["total"]
                or 0
            )
            max_score = thematic_area.activities.count() * 10
            place_percentage = (total_score / max_score) * 100 if max_score > 0 else 0

            status_completion.setdefault(thematic_area.name, {})[place.name] = round(
                place_percentage, 2
            )

            latest_status = (
                ImplementationStatus.objects.filter(
                    activity__thematic_area=thematic_area, place=place
                )
                .order_by("-date_updated")
                .first()
            )
            latest_date = (
                latest_status.date_updated.strftime("%Y-%m-%d")
                if latest_status and latest_status.date_updated
                else "N/A"
            )

            latest_updates.setdefault(thematic_area.name, {})[place.name] = latest_date

    filename = f"{campaign.name}_{region.name}-preparedness_{current_date}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    writer.writerow(
        [
            "Campaign",
            "Round",
            "SIA Start Date",
            "Type of Vaccine",
            "Timeline before SIA",
            "Region",
            "District",
            "Thematic Area",
            "Implementation Status (%)",
            "Date Updated",
        ]
    )

    for thematic_area_name, place_scores in status_completion.items():
        for place_name, implementation_status in place_scores.items():

            date_updated = latest_updates[thematic_area_name].get(place_name, "N/A")

            writer.writerow(
                [
                    campaign.name,
                    campaign.round_number,
                    campaign.sia_start_date.strftime("%Y-%m-%d"),
                    campaign.type_of_vaccine,
                    weeks_to_campaign,
                    region.name,
                    place_name,
                    thematic_area_name,
                    implementation_status,
                    date_updated,
                ]
            )

    return response


@login_required
@restrict_access(allowed_roles=["national"])
def regional_scores_dashboard(request):

    campaign = Campaign.objects.filter(is_active=True).first()

    if not campaign:

        thematic_areas = []
        total_completion_percentages = {}
        regions = []
        status_of_preparedness = {}
        messages.warning(request, "There is currently no active campaign.")
        return render(
            request,
            "campaign/regional_scores_dashboard.html",
            {
                "campaign": campaign,
                "campaign_name": "No Active Campaign",
                "thematic_areas": thematic_areas,
                "regions": regions,
                "total_completion_percentages": total_completion_percentages,
                "status_of_preparedness": status_of_preparedness,
            },
        )

    thematic_areas = ThematicArea.objects.filter(
        campaign=campaign, level="regional"
    ).prefetch_related("activities")

    regions = Region.objects.filter(places__in=campaign.places.all()).distinct()

    total_completion_percentages = {}
    status_of_preparedness = {}

    num_thematic_areas = thematic_areas.count()

    for region in regions:

        region_places = region.places.filter(
            id__in=campaign.places.values_list("id", flat=True)
        )
        total_completion_percentages[region.name] = {}
        sum_percentages = 0

        for thematic_area in thematic_areas:
            total_score_all_places = 0
            total_possible_all_places = (
                len(region_places) * thematic_area.activities.count() * 10
            )

            for activity in thematic_area.activities.all():
                for place in region_places:
                    status = ImplementationStatus.objects.filter(
                        activity=activity, place=place
                    ).first()
                    total_score_all_places += status.scale if status else 0

            total_completion_percentage = (
                (total_score_all_places / total_possible_all_places) * 100
                if total_possible_all_places > 0
                else 0
            )
            total_completion_percentages[region.name][thematic_area.name] = round(
                total_completion_percentage, 2
            )

            sum_percentages += total_completion_percentage

        status_percentage = (
            sum_percentages / num_thematic_areas if num_thematic_areas > 0 else 0
        )
        status_of_preparedness[region.name] = round(status_percentage, 2)

    return render(
        request,
        "campaign/regional_scores_dashboard.html",
        {
            "campaign": campaign,
            "campaign_name": campaign.name if campaign else "No Active Campaign",
            "thematic_areas": thematic_areas,
            "regions": regions,
            "total_completion_percentages": total_completion_percentages,
            "status_of_preparedness": status_of_preparedness,
        },
    )


@login_required
def update_thematic_area_status(request, thematic_area_id):
    if request.method == "POST":

        thematic_area = get_object_or_404(ThematicArea, id=thematic_area_id)
        campaign = Campaign.objects.filter(is_active=True).first()

        if not campaign:
            return redirect("national_dashboard")

        allowed_scales = [0, 5, 10]

        activities = thematic_area.activities.all()
        for activity in activities:

            status, created = NationalImplementationStatus.objects.get_or_create(
                activity=activity, campaign=campaign
            )

            scale_field = f"scale_{activity.id}"
            if scale_field in request.POST:
                try:
                    scale_value = int(request.POST[scale_field])
                    if scale_value not in allowed_scales:

                        return redirect("national_dashboard")
                    status.scale = scale_value
                except ValueError:
                    status.scale = 0

            comments_field = f"comments_{activity.id}"
            if comments_field in request.POST:
                status.comments = request.POST[comments_field]

            status.save()

    return redirect("national_dashboard")


@login_required
@restrict_access(allowed_roles=["national"])
def edit_thematic_area(request, thematic_area_id):
    if request.user.role != "national":
        return redirect("main_page")

    campaign = Campaign.objects.filter(is_active=True).first()
    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return redirect("national_dashboard")

    thematic_area = get_object_or_404(
        ThematicArea, id=thematic_area_id, campaign=campaign
    )
    activities = thematic_area.activities.all()

    if request.method == "POST":

        delete_list = request.POST.get("delete_list", "").split(",")

        for activity_id in delete_list:
            if activity_id:
                activity_to_delete = Activity.objects.filter(
                    id=activity_id, thematic_area=thematic_area
                ).first()
                if activity_to_delete:
                    activity_to_delete.delete()

        thematic_area_form = ThematicAreaForm(request.POST, instance=thematic_area)
        if thematic_area_form.is_valid():
            thematic_area_form.save()

            for activity in activities:
                activity_name = request.POST.get(f"activity_name_{activity.id}")
                if activity_name:
                    activity.name = activity_name
                    activity.save()

            messages.success(
                request, "Thematic area and activities updated successfully."
            )
            return redirect("manage_thematic_areas")

    else:
        thematic_area_form = ThematicAreaForm(instance=thematic_area)

    return render(
        request,
        "campaign/edit_thematic_area.html",
        {
            "thematic_area": thematic_area,
            "thematic_area_form": thematic_area_form,
            "activities": activities,
        },
    )


@login_required
@restrict_access(allowed_roles=["national"])
def edit_region(request, region_id):
    if request.user.role != "national":
        return redirect("main_page")

    region = get_object_or_404(Region, id=region_id)
    places = region.places.all()

    if request.method == "POST":

        delete_place_id = next(
            (
                key.split("_")[-1]
                for key in request.POST
                if key.startswith("delete_place_")
            ),
            None,
        )
        if delete_place_id:
            place_to_delete = get_object_or_404(
                Place, id=delete_place_id, region=region
            )
            place_to_delete.delete()
            messages.success(request, "Place deleted successfully.")
            return redirect("edit_region", region_id=region_id)

        new_region_name = request.POST.get("region_name")
        if new_region_name:
            region.name = new_region_name
            region.save()

        for place in places:
            new_place_name = request.POST.get(f"place_name_{place.id}")
            if new_place_name:
                place.name = new_place_name
                place.save()

        messages.success(request, "Region and places updated successfully.")
        return redirect("manage_regions")

    return render(
        request,
        "campaign/edit_region.html",
        {
            "region": region,
            "places": places,
        },
    )


@login_required
def update_regional_timeline(request):
    if request.method == "POST":
        activity_id = request.POST.get("activity_id")
        timeline_before_sia = request.POST.get("timeline_before_sia")
        try:
            activity = Activity.objects.get(id=activity_id)
            activity.timeline_before_sia = timeline_before_sia
            activity.save()
            return JsonResponse({"status": "success"})
        except Activity.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Activity not found"}, status=404
            )
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


@login_required
def update_national_timeline(request):
    if request.method == "POST":
        activity_id = request.POST.get("activity_id")
        timeline_before_sia = request.POST.get("timeline_before_sia")

        try:
            activity = Activity.objects.get(id=activity_id)
            activity.timeline_before_sia = timeline_before_sia
            activity.save()
            return JsonResponse({"status": "success"})
        except Activity.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Activity not found"}, status=404
            )
        except ValueError:
            return JsonResponse(
                {"status": "error", "message": "Invalid activity ID"}, status=400
            )

    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


@login_required
def update_thematic_area_comments(request):
    if request.method == "POST":
        thematic_area_id = request.POST.get("thematic_area_id")
        comments = request.POST.get("comments")

        try:
            thematic_area = ThematicArea.objects.get(id=thematic_area_id)
            thematic_area.comments = comments
            thematic_area.save()
            return JsonResponse({"status": "success"})
        except ThematicArea.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Thematic area not found"}, status=404
            )

    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


@login_required
@restrict_access(allowed_roles=["national"])
def export_csv(request):
    if request.user.role != "national":
        return redirect("main_page")

    campaign = Campaign.objects.filter(is_active=True).first()
    current_date = timezone.now().date()

    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return redirect("regional_preparedness")

    days_to_campaign = (
        (campaign.sia_start_date - current_date).days if campaign else None
    )
    weeks_to_campaign = (
        f"{days_to_campaign // 7} week(s)" if days_to_campaign is not None else "N/A"
    )

    regions = Region.objects.filter(places__in=campaign.places.all()).distinct()

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{campaign.name}_Regional-preparedness_{current_date}.csv"'
    )

    writer = csv.writer(response)

    writer.writerow(
        [
            "Campaign",
            "Round",
            "SIA Start Date",
            "Type of Vaccine",
            "Timeline before SIA",
            "Region",
            "District",
            "Thematic Area",
            "Implementation Status (%)",
            "Date Updated",
        ]
    )

    for region in regions:
        thematic_areas = ThematicArea.objects.filter(
            campaign=campaign, level="regional"
        ).prefetch_related("activities")
        for thematic_area in thematic_areas:
            for place in region.places.filter(
                id__in=campaign.places.values_list("id", flat=True)
            ):

                total_score = (
                    ImplementationStatus.objects.filter(
                        activity__thematic_area=thematic_area, place=place
                    ).aggregate(total=Sum("scale"))["total"]
                    or 0
                )
                max_score = thematic_area.activities.count() * 10
                implementation_status = (
                    (total_score / max_score) * 100 if max_score > 0 else 0
                )

                latest_status = (
                    ImplementationStatus.objects.filter(
                        activity__thematic_area=thematic_area, place=place
                    )
                    .order_by("-date_updated")
                    .first()
                )
                date_updated = (
                    latest_status.date_updated.strftime("%Y-%m-%d")
                    if latest_status and latest_status.date_updated
                    else "N/A"
                )

                writer.writerow(
                    [
                        campaign.name,
                        campaign.round_number,
                        campaign.sia_start_date.strftime("%Y-%m-%d"),
                        campaign.type_of_vaccine,
                        weeks_to_campaign,
                        region.name,
                        place.name,
                        thematic_area.name,
                        round(implementation_status, 2),
                        date_updated,
                    ]
                )

    return response


def place_login(request):
    if request.method == "POST":
        form = PlaceLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)

            if user is not None and user.role == "place":

                region = user.region
                place = user.place

                login(request, user)
                return redirect("regional_dashboard")

            else:
                messages.error(
                    request,
                    "Invalid username or password.",
                    extra_tags="place_login_error",
                )
    else:
        form = PlaceLoginForm()

    return render(request, "campaign/place_login.html", {"form": form})


@login_required
@restrict_access(allowed_roles=["national"])
def export_csv_national(request):
    if request.user.role != "national":
        return redirect("main_page")

    campaign = Campaign.objects.filter(is_active=True).first()
    current_date = timezone.now().date()

    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return redirect("national_dashboard")

    days_to_campaign = (
        (campaign.sia_start_date - current_date).days if campaign else None
    )
    weeks_to_campaign = (
        f"{days_to_campaign // 7} week(s)" if days_to_campaign is not None else "N/A"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{campaign.name}_National-preparedness_{current_date}.csv"'
    )

    writer = csv.writer(response)

    writer.writerow(
        [
            "Campaign",
            "Round",
            "SIA Start Date",
            "Type of Vaccine",
            "Timeline before SIA",
            "Thematic Area",
            "Implementation Status (%)",
            "Date Updated",
        ]
    )

    thematic_areas = ThematicArea.objects.filter(campaign=campaign, level="national")

    for thematic_area in thematic_areas:

        total_score = (
            NationalImplementationStatus.objects.filter(
                activity__thematic_area=thematic_area, campaign=campaign
            ).aggregate(total=Sum("scale"))["total"]
            or 0
        )
        max_score = thematic_area.activities.count() * 10
        implementation_status = (total_score / max_score) * 100 if max_score > 0 else 0

        latest_status = (
            NationalImplementationStatus.objects.filter(
                activity__thematic_area=thematic_area, campaign=campaign
            )
            .order_by("-date_updated")
            .first()
        )
        date_updated = (
            latest_status.date_updated.strftime("%Y-%m-%d")
            if latest_status and latest_status.date_updated
            else "N/A"
        )

        writer.writerow(
            [
                campaign.name,
                campaign.round_number,
                campaign.sia_start_date.strftime("%Y-%m-%d"),
                campaign.type_of_vaccine,
                weeks_to_campaign,
                thematic_area.name,
                round(implementation_status, 2),
                date_updated,
            ]
        )

    return response


@login_required
@restrict_access(allowed_roles=["national"])
def activity_trend(request):

    campaign = Campaign.objects.filter(is_active=True).first()
    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return redirect("national_dashboard")

    selected_region = request.GET.get("region")
    selected_place = request.GET.get("place")

    regions = Region.objects.filter(places__in=campaign.places.all()).distinct()
    places = (
        Place.objects.filter(region_id=selected_region, id__in=campaign.places.all())
        if selected_region
        else Place.objects.none()
    )

    active_places = campaign.places.all()
    if selected_region:
        active_places = active_places.filter(region_id=selected_region)
    if selected_place:
        active_places = active_places.filter(id=selected_place)

    timeline_brackets = {
        "8 weeks+": 70,
        "8 weeks": 56,
        "6 weeks": 42,
        "4 weeks": 28,
        "2 weeks": 14,
        "1 week": 7,
        "0 weeks": 0,
    }

    days_to_sia = max(0, (campaign.sia_start_date - timezone.now().date()).days)

    historical_scales = HistoricalScale.objects.filter(
        campaign=campaign, place__in=active_places
    )

    daily_counts = {day: 0 for day in range(70, -1, -1)}

    for record in historical_scales:
        days_until_sia = (campaign.sia_start_date - record.date_updated.date()).days
        if 0 <= days_until_sia <= 70:
            daily_counts[days_until_sia] += 1

    trend_data = []
    for day in range(70, days_to_sia - 1, -1):
        trend_data.append(daily_counts[day])

    trend_labels = list(timeline_brackets.keys())
    bracket_indices = [70 - days for days in timeline_brackets.values()]

    return render(
        request,
        "campaign/activity_trend.html",
        {
            "trend_labels": json.dumps(trend_labels),
            "trend_data": json.dumps(trend_data),
            "bracket_indices": json.dumps(bracket_indices),
            "regions": regions,
            "places": places,
            "selected_region": selected_region,
            "selected_place": selected_place,
            "campaign": campaign,
        },
    )


@login_required
@restrict_access(allowed_roles=["national"])
def district_participation_trend(request):

    campaign = Campaign.objects.filter(is_active=True).first()
    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return redirect("national_dashboard")

    active_places = campaign.places.all()

    max_districts = active_places.count()

    timeline_brackets = {
        "8 weeks+": 70,
        "8 weeks": 56,
        "6 weeks": 42,
        "4 weeks": 28,
        "2 weeks": 14,
        "1 week": 7,
        "0 weeks": 0,
    }

    days_to_sia = max(0, (campaign.sia_start_date - timezone.now().date()).days)

    historical_scales = HistoricalScale.objects.filter(
        campaign=campaign, place__in=active_places
    )

    daily_districts = defaultdict(set)

    for record in historical_scales:
        days_until_sia = (campaign.sia_start_date - record.date_updated.date()).days
        daily_districts[days_until_sia].add(record.place.id)

    trend_data = []
    cumulative_districts = set()

    for day in range(70, days_to_sia - 1, -1):

        cumulative_districts.update(daily_districts[day])
        trend_data.append(len(cumulative_districts))

    trend_labels = list(timeline_brackets.keys())
    bracket_indices = [70 - days for days in timeline_brackets.values()]

    return render(
        request,
        "campaign/district_participation_trend.html",
        {
            "trend_labels": json.dumps(trend_labels),
            "trend_data": json.dumps(trend_data),
            "bracket_indices": json.dumps(bracket_indices),
            "max_districts": max_districts,
            "campaign": campaign,
        },
    )


@login_required
@restrict_access(allowed_roles=["national"])
def trend_selection(request):
    return render(request, "campaign/trend_selection.html")


@login_required
def get_places_by_region(request):
    region_id = request.GET.get("region_id")
    if region_id:
        places = Place.objects.filter(
            region_id=region_id,
            id__in=Campaign.objects.filter(is_active=True).values("places"),
        ).values("id", "name")
        return JsonResponse(list(places), safe=False)
    return JsonResponse([], safe=False)


@login_required
@restrict_access(allowed_roles=["regional"])
def regional_activity_trend(request):

    if request.user.role != "regional":
        return redirect("main_page")

    campaign = Campaign.objects.filter(is_active=True).first()
    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return redirect("regional_dashboard")

    selected_place = request.GET.get("place")

    region = request.user.region
    places_in_region = region.places.filter(
        id__in=campaign.places.values_list("id", flat=True)
    )

    active_places = places_in_region
    if selected_place:
        active_places = active_places.filter(id=selected_place)

    timeline_brackets = {
        "8 weeks+": 70,
        "8 weeks": 56,
        "6 weeks": 42,
        "4 weeks": 28,
        "2 weeks": 14,
        "1 week": 7,
        "0 weeks": 0,
    }

    days_to_sia = max(0, (campaign.sia_start_date - timezone.now().date()).days)

    historical_scales = HistoricalScale.objects.filter(
        campaign=campaign, place__in=active_places
    )

    daily_counts = {day: 0 for day in range(70, -1, -1)}

    for record in historical_scales:
        days_until_sia = (campaign.sia_start_date - record.date_updated.date()).days
        if 0 <= days_until_sia <= 70:
            daily_counts[days_until_sia] += 1

    trend_data = [daily_counts[day] for day in range(70, days_to_sia - 1, -1)]

    trend_labels = list(timeline_brackets.keys())
    bracket_indices = [70 - days for days in timeline_brackets.values()]

    return render(
        request,
        "campaign/regional_activity_trend.html",
        {
            "trend_labels": json.dumps(trend_labels),
            "trend_data": json.dumps(trend_data),
            "bracket_indices": json.dumps(bracket_indices),
            "campaign": campaign,
            "places": places_in_region,
            "selected_place": selected_place,
        },
    )


@login_required
@restrict_access(allowed_roles=["regional"])
def regional_district_participation_trend(request):

    if request.user.role != "regional":
        return redirect("main_page")

    campaign = Campaign.objects.filter(is_active=True).first()
    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return redirect("regional_dashboard")

    region = request.user.region
    places_in_region = region.places.filter(
        id__in=campaign.places.values_list("id", flat=True)
    )

    max_districts = places_in_region.count()

    timeline_brackets = {
        "8 weeks+": 70,
        "8 weeks": 56,
        "6 weeks": 42,
        "4 weeks": 28,
        "2 weeks": 14,
        "1 week": 7,
        "0 weeks": 0,
    }

    days_to_sia = max(0, (campaign.sia_start_date - timezone.now().date()).days)

    historical_scales = HistoricalScale.objects.filter(
        campaign=campaign, place__in=places_in_region
    )

    daily_districts = defaultdict(set)

    for record in historical_scales:
        days_until_sia = (campaign.sia_start_date - record.date_updated.date()).days
        if 0 <= days_until_sia <= 70:
            daily_districts[days_until_sia].add(record.place.id)

    trend_data = []
    cumulative_districts = set()

    for day in range(70, days_to_sia - 1, -1):

        cumulative_districts.update(daily_districts[day])
        trend_data.append(len(cumulative_districts))

    trend_labels = list(timeline_brackets.keys())
    bracket_indices = [70 - days for days in timeline_brackets.values()]

    return render(
        request,
        "campaign/regional_district_participation_trend.html",
        {
            "trend_labels": json.dumps(trend_labels),
            "trend_data": json.dumps(trend_data),
            "bracket_indices": json.dumps(bracket_indices),
            "max_districts": max_districts,
            "campaign": campaign,
        },
    )


@login_required
@restrict_access(allowed_roles=["regional"])
def regional_trend_selection(request):
    if request.user.role != "regional":
        return redirect("main_page")
    return render(request, "campaign/regional_trend_selection.html")


@login_required
@restrict_access(allowed_roles=["regional"])
def regional_manage_places(request):
    if request.user.role != "regional":
        return redirect("main_page")

    places = request.user.region.places.prefetch_related("user_set")

    return render(request, "campaign/regional_manage_places.html", {"places": places})


@login_required
@restrict_access(allowed_roles=["regional"])
def regional_assign_place_user(request, place_id):

    place = get_object_or_404(Place, id=place_id, region=request.user.region)
    region = place.region

    created_user = None

    if request.method == "POST":
        form = PlaceUserCreationForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.role = "place"
            user.place = place
            user.region = region

            raw_password = form.cleaned_data.get("password1")
            user.set_password(raw_password)
            user.save()

            created_user = {"username": user.username, "password": raw_password}
            messages.success(request, "Place user assigned successfully.")
            return render(
                request,
                "campaign/regional_assign_place_user.html",
                {
                    "form": PlaceUserCreationForm(),
                    "place": place,
                    "created_user": created_user,
                },
            )

    else:
        form = PlaceUserCreationForm()

    return render(
        request,
        "campaign/regional_assign_place_user.html",
        {"form": form, "place": place},
    )


@login_required
@restrict_access(allowed_roles=["regional"])
def regional_delete_place_user(request, user_id):

    user = get_object_or_404(
        User, id=user_id, role="place", place__region=request.user.region
    )

    if request.method == "POST":
        user.delete()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error"}, status=400)


@login_required
@restrict_access(allowed_roles=["national"])
def manage_national_users(request):
    if request.user.role != "national":
        return redirect("main_page")

    if request.method == "POST" and "user_id" in request.POST:
        user_id = request.POST["user_id"]
        user = get_object_or_404(User, id=user_id, role="national")
        user.delete()
        messages.success(request, "National user deleted successfully.")

    national_users = User.objects.filter(role="national")
    return render(
        request,
        "campaign/manage_national_users.html",
        {"national_users": national_users},
    )


@login_required
@restrict_access(allowed_roles=["national"])
def create_national_user(request):
    if request.user.role != "national":
        return redirect("main_page")

    created_user = None
    if request.method == "POST":
        form = NationalUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = "national"
            raw_password = form.cleaned_data.get("password1")
            user.set_password(raw_password)
            user.save()

            created_user = {"username": user.username, "password": raw_password}
            messages.success(request, "National user created successfully.")
            return render(
                request,
                "campaign/create_national_user.html",
                {"form": NationalUserCreationForm(), "created_user": created_user},
            )
    else:
        form = NationalUserCreationForm()

    return render(
        request,
        "campaign/create_national_user.html",
        {"form": form, "created_user": created_user},
    )


@login_required
@restrict_access(allowed_roles=["national"])
def combined_dashboard(request):
    campaign = Campaign.objects.filter(is_active=True).first()
    current_date = timezone.now().date()

    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return render(
            request,
            "campaign/dashboard.html",
            {
                "campaign": None,
                "campaign_name": "No Active Campaign",
                "days_to_campaign": None,
                "weeks_to_campaign": None,
                "thematic_data_national": {},
                "status_of_preparedness": None,
                "overall_readiness": None,
                "regional_readiness_with_thematics": {},
                "thematic_data_regional": {},
                "top_regions": [],
                "bottom_regions": [],
                "top_places": [],
                "bottom_places": [],
            },
        )

    days_to_campaign = (campaign.sia_start_date - current_date).days
    weeks_to_campaign = days_to_campaign // 7

    thematic_areas_national = (
        ThematicArea.objects.filter(campaign=campaign, level="national")
        .order_by("name")
        .prefetch_related("activities")
    )

    thematic_data_national = {
        "labels": [],
        "values": [],
    }

    thematic_status_national = []
    for thematic_area in thematic_areas_national:
        total_score = 0
        max_total = thematic_area.activities.count() * 10

        for activity in thematic_area.activities.all():
            status = NationalImplementationStatus.objects.filter(
                activity=activity, campaign=campaign
            ).first()
            if status:
                total_score += status.scale

        total_percentage = (
            round((total_score / max_total) * 100, 2) if max_total > 0 else 0
        )
        thematic_data_national["labels"].append(thematic_area.name)
        thematic_data_national["values"].append(total_percentage)
        thematic_status_national.append(
            {"name": thematic_area.name, "percentage": total_percentage}
        )

    status_of_preparedness = (
        round(
            sum(item["percentage"] for item in thematic_status_national)
            / len(thematic_status_national),
            2,
        )
        if thematic_status_national
        else 0
    )

    regions = Region.objects.filter(places__in=campaign.places.all()).distinct()
    thematic_areas_regional = ThematicArea.objects.filter(
        campaign=campaign, level="regional"
    ).prefetch_related("activities")

    thematic_data_regional = {
        "labels": [],
        "values": [],
    }
    thematic_totals = {ta.name: 0 for ta in thematic_areas_regional}
    regional_readiness_with_thematics = []

    for region in regions:
        places = region.places.filter(
            id__in=campaign.places.values_list("id", flat=True)
        )

        regional_total_percentage = 0
        thematic_scores = {}

        for thematic_area in thematic_areas_regional:
            total_score_all_places = 0
            total_possible_all_places = (
                len(places) * thematic_area.activities.count() * 10
            )

            for activity in thematic_area.activities.all():
                for place in places:
                    status = ImplementationStatus.objects.filter(
                        activity=activity, place=place
                    ).first()
                    total_score_all_places += status.scale if status else 0

            thematic_percentage = (
                (total_score_all_places / total_possible_all_places) * 100
                if total_possible_all_places > 0
                else 0
            )
            thematic_scores[thematic_area.name] = round(thematic_percentage, 2)
            regional_total_percentage += thematic_percentage
            thematic_totals[thematic_area.name] += thematic_percentage

        regional_average = (
            regional_total_percentage / len(thematic_areas_regional)
            if thematic_areas_regional
            else 0
        )
        regional_readiness_with_thematics.append(
            {
                "region": region.name,
                "thematic_scores": thematic_scores,
                "preparedness": round(regional_average, 2),
            }
        )

    thematic_data_regional["labels"] = [ta.name for ta in thematic_areas_regional]
    thematic_data_regional["values"] = [
        round(thematic_totals[ta.name] / len(regions), 2)
        for ta in thematic_areas_regional
    ]

    top_regions = [
        region
        for region in regional_readiness_with_thematics
        if region["preparedness"] >= 70
    ]
    top_regions = sorted(top_regions, key=lambda x: x["preparedness"], reverse=True)

    bottom_regions = [
        region
        for region in regional_readiness_with_thematics
        if region["preparedness"] <= 40
    ]
    bottom_regions = sorted(
        bottom_regions, key=lambda x: x["preparedness"], reverse=True
    )

    places = Place.objects.filter(id__in=campaign.places.values_list("id", flat=True))
    place_readiness_list = []

    for place in places:
        total_place_percentage = 0

        for thematic_area in thematic_areas_regional:
            total_score = (
                ImplementationStatus.objects.filter(
                    activity__thematic_area=thematic_area, place=place
                ).aggregate(total=Sum("scale"))["total"]
                or 0
            )
            max_score = thematic_area.activities.count() * 10
            thematic_percentage = (
                (total_score / max_score) * 100 if max_score > 0 else 0
            )
            total_place_percentage += thematic_percentage

        place_average = (
            total_place_percentage / len(thematic_areas_regional)
            if thematic_areas_regional
            else 0
        )
        place_readiness_list.append(
            {"place": place.name, "preparedness": round(place_average, 2)}
        )

    top_places = [
        place for place in place_readiness_list if place["preparedness"] >= 70
    ]
    top_places = sorted(top_places, key=lambda x: x["preparedness"], reverse=True)

    bottom_places = [
        place for place in place_readiness_list if place["preparedness"] <= 40
    ]
    bottom_places = sorted(bottom_places, key=lambda x: x["preparedness"], reverse=True)

    overall_readiness = round(
        sum(region["preparedness"] for region in regional_readiness_with_thematics)
        / len(regional_readiness_with_thematics),
        2,
    )

    return render(
        request,
        "campaign/dashboard.html",
        {
            "campaign": campaign,
            "campaign_name": campaign.name if campaign else "No Active Campaign",
            "days_to_campaign": days_to_campaign,
            "weeks_to_campaign": weeks_to_campaign,
            "thematic_data_national": thematic_data_national,
            "status_of_preparedness": status_of_preparedness,
            "overall_readiness": overall_readiness,
            "regional_readiness_with_thematics": regional_readiness_with_thematics,
            "thematic_area_names": [ta.name for ta in thematic_areas_regional],
            "thematic_data_regional": thematic_data_regional,
            "top_regions": top_regions,
            "bottom_regions": bottom_regions,
            "top_places": top_places,
            "bottom_places": bottom_places,
            "current_date": current_date,
            "round_number": campaign.round_number if campaign else None,
        },
    )


matplotlib.use("Agg")


@login_required
@restrict_access(allowed_roles=["national"])
def combined_dashboard_pdf(request):
    campaign = Campaign.objects.filter(is_active=True).first()
    current_date = timezone.now().date()

    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return HttpResponse("No active campaign found", content_type="text/plain")

    days_to_campaign = (campaign.sia_start_date - current_date).days
    weeks_to_campaign = days_to_campaign // 7

    thematic_areas_national = (
        ThematicArea.objects.filter(campaign=campaign, level="national")
        .order_by("name")
        .prefetch_related("activities")
    )

    thematic_data_national = {
        "labels": [],
        "values": [],
    }

    thematic_status_national = []
    for thematic_area in thematic_areas_national:
        total_score = 0
        max_total = thematic_area.activities.count() * 10

        for activity in thematic_area.activities.all():
            status = NationalImplementationStatus.objects.filter(
                activity=activity, campaign=campaign
            ).first()
            if status:
                total_score += status.scale

        total_percentage = (
            round((total_score / max_total) * 100, 2) if max_total > 0 else 0
        )
        thematic_data_national["labels"].append(thematic_area.name)
        thematic_data_national["values"].append(total_percentage)
        thematic_status_national.append(
            {"name": thematic_area.name, "percentage": total_percentage}
        )

    status_of_preparedness = (
        round(
            sum(item["percentage"] for item in thematic_status_national)
            / len(thematic_status_national),
            2,
        )
        if thematic_status_national
        else 0
    )

    regions = Region.objects.filter(places__in=campaign.places.all()).distinct()
    thematic_areas_regional = ThematicArea.objects.filter(
        campaign=campaign, level="regional"
    ).prefetch_related("activities")

    thematic_data_regional = {
        "labels": [],
        "values": [],
    }
    thematic_totals = {ta.name: 0 for ta in thematic_areas_regional}
    regional_readiness_with_thematics = []

    for region in regions:
        places = region.places.filter(
            id__in=campaign.places.values_list("id", flat=True)
        )

        regional_total_percentage = 0
        thematic_scores = {}

        for thematic_area in thematic_areas_regional:
            total_score_all_places = 0
            total_possible_all_places = (
                len(places) * thematic_area.activities.count() * 10
            )

            for activity in thematic_area.activities.all():
                for place in places:
                    status = ImplementationStatus.objects.filter(
                        activity=activity, place=place
                    ).first()
                    total_score_all_places += status.scale if status else 0

            thematic_percentage = (
                (total_score_all_places / total_possible_all_places) * 100
                if total_possible_all_places > 0
                else 0
            )
            thematic_scores[thematic_area.name] = round(thematic_percentage, 2)
            regional_total_percentage += thematic_percentage
            thematic_totals[thematic_area.name] += thematic_percentage

        regional_average = (
            regional_total_percentage / len(thematic_areas_regional)
            if thematic_areas_regional
            else 0
        )
        regional_readiness_with_thematics.append(
            {
                "region": region.name,
                "thematic_scores": thematic_scores,
                "preparedness": round(regional_average, 2),
            }
        )

    thematic_data_regional["labels"] = [ta.name for ta in thematic_areas_regional]
    thematic_data_regional["values"] = [
        round(thematic_totals[ta.name] / len(regions), 2)
        for ta in thematic_areas_regional
    ]

    top_regions = [
        region
        for region in regional_readiness_with_thematics
        if region["preparedness"] >= 70
    ]
    top_regions = sorted(top_regions, key=lambda x: x["preparedness"], reverse=True)

    bottom_regions = [
        region
        for region in regional_readiness_with_thematics
        if region["preparedness"] <= 40
    ]
    bottom_regions = sorted(
        bottom_regions, key=lambda x: x["preparedness"], reverse=True
    )

    places = Place.objects.filter(id__in=campaign.places.values_list("id", flat=True))
    place_readiness_list = []

    for place in places:
        total_place_percentage = 0

        for thematic_area in thematic_areas_regional:
            total_score = (
                ImplementationStatus.objects.filter(
                    activity__thematic_area=thematic_area, place=place
                ).aggregate(total=Sum("scale"))["total"]
                or 0
            )
            max_score = thematic_area.activities.count() * 10
            thematic_percentage = (
                (total_score / max_score) * 100 if max_score > 0 else 0
            )
            total_place_percentage += thematic_percentage

        place_average = (
            total_place_percentage / len(thematic_areas_regional)
            if thematic_areas_regional
            else 0
        )
        place_readiness_list.append(
            {"place": place.name, "preparedness": round(place_average, 2)}
        )

    top_places = [
        place for place in place_readiness_list if place["preparedness"] >= 70
    ]
    top_places = sorted(top_places, key=lambda x: x["preparedness"], reverse=True)

    bottom_places = [
        place for place in place_readiness_list if place["preparedness"] <= 40
    ]
    bottom_places = sorted(bottom_places, key=lambda x: x["preparedness"], reverse=True)

    overall_readiness = round(
        sum(region["preparedness"] for region in regional_readiness_with_thematics)
        / len(regional_readiness_with_thematics),
        2,
    )

    def create_circular_chart(percentage, title):
        plt.figure(figsize=(6, 6))
        sizes = [percentage, 100 - percentage]
        colors = (
            ["#28a745", "#E5E7EB"]
            if percentage >= 70
            else ["#ffc107", "#E5E7EB"] if percentage > 40 else ["#dc3545", "#E5E7EB"]
        )
        plt.pie(
            sizes,
            colors=colors,
            startangle=90,
            counterclock=False,
            wedgeprops=dict(width=0.5),
        )
        plt.title(title, fontsize=14)

        plt.text(
            0,
            0,
            f"{percentage}%",
            ha="center",
            va="center",
            fontsize=20,
            fontweight="bold",
        )
        plt.tight_layout()
        buffer = BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        chart_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close()
        return chart_image

    def create_bar_chart(labels, values, title, color):

        sorted_data = sorted(zip(labels, values), key=lambda x: x[1], reverse=True)
        sorted_labels, sorted_values = zip(*sorted_data)

        plt.figure(figsize=(8, 6))
        bars = plt.bar(sorted_labels, sorted_values, color=color)
        plt.xlabel("Thematic Areas")
        plt.ylabel("Readiness (%)")
        plt.title(title, fontsize=14)
        plt.xticks(rotation=45, ha="right")

        for bar in bars:
            height = bar.get_height()
            if height > 10:
                plt.annotate(
                    f"{height:.1f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, height / 2),
                    xytext=(0, 0),
                    textcoords="offset points",
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=10,
                    weight="bold",
                )
            else:
                plt.annotate(
                    f"{height:.1f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, height + 1),
                    xytext=(0, 0),
                    textcoords="offset points",
                    ha="center",
                    va="center",
                    color=color,
                    fontsize=10,
                )
        plt.tight_layout()
        buffer = BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        chart_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close()
        return chart_image

    circular_chart_national = create_circular_chart(
        status_of_preparedness, "National Preparedness"
    )
    overall_readiness_chart = create_circular_chart(
        overall_readiness, "Regional Preparedness"
    )
    thematic_bar_chart_national = create_bar_chart(
        thematic_data_national["labels"],
        thematic_data_national["values"],
        "National Thematic Areas",
        "#4169E1",
    )
    thematic_bar_chart_regional = create_bar_chart(
        thematic_data_regional["labels"],
        thematic_data_regional["values"],
        "Regional Thematic Areas",
        "#008080",
    )

    context = {
        "campaign": campaign,
        "campaign_name": campaign.name if campaign else "No Active Campaign",
        "days_to_campaign": days_to_campaign,
        "weeks_to_campaign": weeks_to_campaign,
        "thematic_data_national": thematic_data_national,
        "status_of_preparedness": status_of_preparedness,
        "overall_readiness": overall_readiness,
        "regional_readiness_with_thematics": regional_readiness_with_thematics,
        "thematic_area_names": [ta.name for ta in thematic_areas_regional],
        "thematic_data_regional": thematic_data_regional,
        "top_regions": top_regions,
        "bottom_regions": bottom_regions,
        "top_places": top_places,
        "bottom_places": bottom_places,
        "current_date": current_date,
        "round_number": campaign.round_number if campaign else None,
        "circular_chart_national": circular_chart_national,
        "overall_readiness_chart": overall_readiness_chart,
        "thematic_bar_chart_national": thematic_bar_chart_national,
        "thematic_bar_chart_regional": thematic_bar_chart_regional,
    }

    html_string = render_to_string("campaign/dashboard_pdf.html", context)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="Readiness_report.pdf"'

    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(
        response,
        stylesheets=[CSS(string="@page { size: A4; margin: 2cm }")],
    )

    return response


@login_required
@restrict_access(allowed_roles=["regional"])
def readiness_analysis_view(request):
    campaign = Campaign.objects.filter(is_active=True).first()
    today = timezone.now().date()

    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return render(
            request,
            "campaign/analysis2.html",
            {
                "campaign": None,
                "top_ready_places": [],
                "least_ready_places": [],
                "highest_ready_place": None,
                "lowest_ready_place": None,
                "regional_readiness_with_thematics": [],
                "thematic_area_names": [],
                "thematic_data_regional": {},
                "overall_readiness": 0,
                "current_date": today,
                "days_to_campaign": None,
            },
        )

    days_to_campaign = (campaign.sia_start_date - today).days

    if request.user.role != "regional":
        messages.error(request, "You are not authorized to view this analysis.")
        return redirect("main_page")

    all_places_in_region = request.user.region.places.all()
    campaign_places = campaign.places.all()
    places = all_places_in_region.filter(
        id__in=campaign_places.values_list("id", flat=True)
    )

    if not places.exists():
        messages.warning(
            request,
            "No places assigned to you are participating in the current campaign.",
        )
        return render(
            request,
            "campaign/analysis2.html",
            {
                "campaign": campaign,
                "top_ready_places": [],
                "least_ready_places": [],
                "highest_ready_place": None,
                "lowest_ready_place": None,
                "regional_readiness_with_thematics": [],
                "thematic_area_names": [],
                "thematic_data_regional": {},
                "overall_readiness": 0,
                "current_date": today,
                "days_to_campaign": days_to_campaign,
            },
        )

    thematic_areas = ThematicArea.objects.filter(campaign=campaign, level="regional")
    thematic_area_names = [ta.name for ta in thematic_areas]
    thematic_data_regional = {"labels": [], "values": []}
    thematic_totals = {thematic_area.name: 0 for thematic_area in thematic_areas}
    regional_readiness_with_thematics = []
    place_readiness = []

    for place in places:
        total_place_percentage = 0
        thematic_scores = {}

        for thematic_area in thematic_areas:
            total_score = (
                ImplementationStatus.objects.filter(
                    activity__thematic_area=thematic_area, place=place
                ).aggregate(total=Sum("scale"))["total"]
                or 0
            )
            max_score = thematic_area.activities.count() * 10
            thematic_percentage = (
                (total_score / max_score) * 100 if max_score > 0 else 0
            )
            thematic_scores[thematic_area.name] = round(thematic_percentage, 2)
            total_place_percentage += thematic_percentage
            thematic_totals[thematic_area.name] += thematic_percentage

        place_average = (
            total_place_percentage / len(thematic_areas) if thematic_areas else 0
        )
        regional_readiness_with_thematics.append(
            {
                "region": place.name,
                "thematic_scores": thematic_scores,
                "preparedness": round(place_average, 2),
            }
        )
        place_readiness.append(
            {"place": place, "preparedness": round(place_average, 2)}
        )

    thematic_data_regional["labels"] = thematic_area_names
    thematic_data_regional["values"] = [
        (
            round(thematic_totals[thematic_area.name] / len(places), 2)
            if len(places) > 0
            else 0
        )
        for thematic_area in thematic_areas
    ]

    overall_readiness = (
        round(
            sum(entry["preparedness"] for entry in regional_readiness_with_thematics)
            / len(regional_readiness_with_thematics),
            2,
        )
        if regional_readiness_with_thematics
        else 0
    )

    top_ready_places = [
        entry for entry in place_readiness if entry["preparedness"] >= 70
    ]
    top_ready_places = sorted(
        top_ready_places, key=lambda x: x["preparedness"], reverse=True
    )

    least_ready_places = [
        entry for entry in place_readiness if entry["preparedness"] <= 40
    ]
    least_ready_places = sorted(
        least_ready_places, key=lambda x: x["preparedness"], reverse=True
    )

    highest_ready_place = (
        max(place_readiness, key=lambda x: x["preparedness"])
        if place_readiness
        else None
    )
    lowest_ready_place = (
        min(place_readiness, key=lambda x: x["preparedness"])
        if place_readiness
        else None
    )

    return render(
        request,
        "campaign/analysis2.html",
        {
            "campaign": campaign,
            "top_ready_places": top_ready_places,
            "least_ready_places": least_ready_places,
            "highest_ready_place": highest_ready_place,
            "lowest_ready_place": lowest_ready_place,
            "regional_readiness_with_thematics": regional_readiness_with_thematics,
            "thematic_area_names": thematic_area_names,
            "thematic_data_regional": thematic_data_regional,
            "overall_readiness": overall_readiness,
            "current_date": today,
            "days_to_campaign": days_to_campaign,
            "regional_preparedness": overall_readiness,
        },
    )


matplotlib.use("Agg")


@login_required
@restrict_access(allowed_roles=["regional"])
def readiness_analysis_pdf(request):
    campaign = Campaign.objects.filter(is_active=True).first()
    today = timezone.now().date()

    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return HttpResponse("No active campaign found", content_type="text/plain")

    days_to_campaign = (campaign.sia_start_date - today).days

    if request.user.role != "regional":
        messages.error(request, "You are not authorized to view this analysis.")
        return HttpResponse(
            "You are not authorized to view this analysis.", content_type="text/plain"
        )

    all_places_in_region = request.user.region.places.all()
    campaign_places = campaign.places.all()
    places = all_places_in_region.filter(
        id__in=campaign_places.values_list("id", flat=True)
    )

    if not places.exists():
        messages.warning(
            request,
            "No places assigned to you are participating in the current campaign.",
        )
        return HttpResponse(
            "No places assigned to you are participating in the current campaign.",
            content_type="text/plain",
        )

    thematic_areas = ThematicArea.objects.filter(campaign=campaign, level="regional")
    thematic_area_names = [ta.name for ta in thematic_areas]
    thematic_data_regional = {"labels": [], "values": []}
    thematic_totals = {thematic_area.name: 0 for thematic_area in thematic_areas}
    regional_readiness_with_thematics = []
    place_readiness = []

    for place in places:
        total_place_percentage = 0
        thematic_scores = {}

        for thematic_area in thematic_areas:
            total_score = (
                ImplementationStatus.objects.filter(
                    activity__thematic_area=thematic_area, place=place
                ).aggregate(total=Sum("scale"))["total"]
                or 0
            )
            max_score = thematic_area.activities.count() * 10
            thematic_percentage = (
                (total_score / max_score) * 100 if max_score > 0 else 0
            )
            thematic_scores[thematic_area.name] = round(thematic_percentage, 2)
            total_place_percentage += thematic_percentage
            thematic_totals[thematic_area.name] += thematic_percentage

        place_average = (
            total_place_percentage / len(thematic_areas) if thematic_areas else 0
        )
        regional_readiness_with_thematics.append(
            {
                "region": place.name,
                "thematic_scores": thematic_scores,
                "preparedness": round(place_average, 2),
            }
        )
        place_readiness.append(
            {"place": place, "preparedness": round(place_average, 2)}
        )

    thematic_data_regional["labels"] = thematic_area_names
    thematic_data_regional["values"] = [
        (
            round(thematic_totals[thematic_area.name] / len(places), 2)
            if len(places) > 0
            else 0
        )
        for thematic_area in thematic_areas
    ]

    overall_readiness = (
        round(
            sum(entry["preparedness"] for entry in regional_readiness_with_thematics)
            / len(regional_readiness_with_thematics),
            2,
        )
        if regional_readiness_with_thematics
        else 0
    )

    top_ready_places = [
        entry for entry in place_readiness if entry["preparedness"] >= 70
    ]
    top_ready_places = sorted(
        top_ready_places, key=lambda x: x["preparedness"], reverse=True
    )

    least_ready_places = [
        entry for entry in place_readiness if entry["preparedness"] <= 40
    ]
    least_ready_places = sorted(
        least_ready_places, key=lambda x: x["preparedness"], reverse=True
    )

    highest_ready_place = (
        max(place_readiness, key=lambda x: x["preparedness"])
        if place_readiness
        else None
    )
    lowest_ready_place = (
        min(place_readiness, key=lambda x: x["preparedness"])
        if place_readiness
        else None
    )

    def create_circular_chart(percentage, title):
        plt.figure(figsize=(6, 6))
        sizes = [percentage, 100 - percentage]
        colors = (
            ["#28a745", "#E5E7EB"]
            if percentage >= 70
            else ["#ffc107", "#E5E7EB"] if percentage > 40 else ["#dc3545", "#E5E7EB"]
        )
        plt.pie(
            sizes,
            colors=colors,
            startangle=90,
            counterclock=False,
            wedgeprops=dict(width=0.5),
        )
        plt.title(title, fontsize=14)
        plt.text(
            0,
            0,
            f"{percentage}%",
            ha="center",
            va="center",
            fontsize=20,
            fontweight="bold",
        )
        plt.tight_layout()
        buffer = BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        chart_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close()
        return chart_image

    def create_bar_chart(labels, values, title, color):
        if not labels or not values:
            return None
        sorted_data = sorted(zip(labels, values), key=lambda x: x[1], reverse=True)
        sorted_labels, sorted_values = zip(*sorted_data)
        plt.figure(figsize=(8, 6))
        bars = plt.bar(sorted_labels, sorted_values, color=color)
        plt.xlabel("Thematic Areas")
        plt.ylabel("Readiness (%)")
        plt.title(title, fontsize=14)
        plt.xticks(rotation=45, ha="right")
        for bar in bars:
            height = bar.get_height()
            if height > 10:
                plt.annotate(
                    f"{height:.1f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, height / 2),
                    xytext=(0, 0),
                    textcoords="offset points",
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=10,
                    weight="bold",
                )
            else:
                plt.annotate(
                    f"{height:.1f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, height + 1),
                    xytext=(0, 0),
                    textcoords="offset points",
                    ha="center",
                    va="center",
                    color=color,
                    fontsize=10,
                )
        plt.tight_layout()
        buffer = BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        chart_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close()
        return chart_image

    overall_readiness_chart = create_circular_chart(
        overall_readiness, "Overall Readiness"
    )
    thematic_bar_chart = create_bar_chart(
        thematic_data_regional["labels"],
        thematic_data_regional["values"],
        "Thematic Areas Readiness",
        "#008080",
    )

    region_name = request.user.region.name

    context = {
        "campaign": campaign,
        "top_ready_places": top_ready_places,
        "least_ready_places": least_ready_places,
        "highest_ready_place": highest_ready_place,
        "lowest_ready_place": lowest_ready_place,
        "regional_readiness_with_thematics": regional_readiness_with_thematics,
        "thematic_area_names": thematic_area_names,
        "thematic_data_regional": thematic_data_regional,
        "overall_readiness": overall_readiness,
        "current_date": today,
        "days_to_campaign": days_to_campaign,
        "regional_preparedness": overall_readiness,
        "overall_readiness_chart": overall_readiness_chart,
        "thematic_bar_chart": thematic_bar_chart,
        "region_name": region_name,
    }

    html_string = render_to_string("campaign/analysis2_pdf.html", context)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="Readiness_analysis.pdf"'

    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(
        response,
        stylesheets=[CSS(string="@page { size: A4; margin: 2cm }")],
    )

    return response


@login_required
@restrict_access(allowed_roles=["place"])
def export_csv_place(request, place_id):
    if request.user.role not in ["place", "regional", "national"]:
        return redirect("main_page")

    campaign = Campaign.objects.filter(is_active=True).first()
    current_date = timezone.now().date()

    if not campaign:
        messages.warning(request, "There is currently no active campaign.")
        return redirect("regional_dashboard")

    place = get_object_or_404(Place, id=place_id)

    if request.user.role == "regional" and place.region != request.user.region:
        return redirect("main_page")
    if request.user.role == "place" and place != request.user.place:
        return redirect("main_page")

    days_to_campaign = (
        (campaign.sia_start_date - current_date).days if campaign else None
    )
    weeks_to_campaign = (
        f"{days_to_campaign // 7} week(s)" if days_to_campaign is not None else "N/A"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{campaign.name}_{place.name}_preparedness_{current_date}.csv"'
    )

    writer = csv.writer(response)

    writer.writerow(
        [
            "Campaign",
            "Round",
            "SIA Start Date",
            "Type of Vaccine",
            "Timeline before SIA",
            "District",
            "Thematic Area",
            "Implementation Status (%)",
            "Date Updated",
        ]
    )

    thematic_areas = ThematicArea.objects.filter(
        campaign=campaign, level="regional"
    ).prefetch_related("activities")

    for thematic_area in thematic_areas:
        total_score = (
            ImplementationStatus.objects.filter(
                activity__thematic_area=thematic_area, place=place
            ).aggregate(total=Sum("scale"))["total"]
            or 0
        )
        max_score = thematic_area.activities.count() * 10
        implementation_status = (total_score / max_score) * 100 if max_score > 0 else 0

        latest_status = (
            ImplementationStatus.objects.filter(
                activity__thematic_area=thematic_area, place=place
            )
            .order_by("-date_updated")
            .first()
        )
        date_updated = (
            latest_status.date_updated.strftime("%Y-%m-%d")
            if latest_status and latest_status.date_updated
            else "N/A"
        )

        writer.writerow(
            [
                campaign.name,
                campaign.round_number,
                campaign.sia_start_date.strftime("%Y-%m-%d"),
                campaign.type_of_vaccine,
                weeks_to_campaign,
                place.name,
                thematic_area.name,
                round(implementation_status, 2),
                date_updated,
            ]
        )

    return response
