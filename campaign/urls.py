from django.urls import path
from . import views

urlpatterns = [
    path("", views.main_page, name="main_page"),
    path("national_login/", views.national_login, name="national_login"),
    path("regional_login/", views.regional_login, name="regional_login"),
    path("logout/", views.user_logout, name="logout"),
    path("national_dashboard/", views.national_dashboard, name="national_dashboard"),
    path("regional_dashboard/", views.regional_dashboard, name="regional_dashboard"),
    path("thematic_areas/", views.manage_thematic_areas, name="manage_thematic_areas"),
    path(
        "thematic_areas/add_activity/<int:thematic_area_id>/",
        views.add_activity,
        name="add_activity",
    ),
    path("regions/", views.manage_regions, name="manage_regions"),
    path(
        "regions/assign_user/<int:region_id>/",
        views.assign_regional_user,
        name="assign_regional_user",
    ),
    path(
        "places/assign_user/<int:place_id>/",
        views.assign_place_user,
        name="assign_place_user",
    ),
    path("regions/add_place/<int:region_id>/", views.add_place, name="add_place"),
    path(
        "regional_preparedness/",
        views.regional_preparedness,
        name="regional_preparedness",
    ),
    path("export_csv/", views.export_csv, name="export_csv"),
    path("export_csv_regional/", views.export_csv_regional, name="export_csv_regional"),
    path("export_csv_national/", views.export_csv_national, name="export_csv_national"),
    path(
        "update_status/",
        views.update_implementation_status,
        name="update_implementation_status",
    ),
    path("regional_scores/", views.regional_scores_dashboard, name="regional_scores"),
    path(
        "campaign/update_thematic_area_status/<int:thematic_area_id>/",
        views.update_thematic_area_status,
        name="update_thematic_area_status",
    ),
    path(
        "edit_thematic_area/<int:thematic_area_id>/",
        views.edit_thematic_area,
        name="edit_thematic_area",
    ),
    path("edit_region/<int:region_id>/", views.edit_region, name="edit_region"),
    path("manage_campaigns/", views.manage_campaigns, name="manage_campaigns"),
    path(
        "manage_campaigns/select_places/",
        views.select_campaign_places,
        name="select_campaign_places",
    ),
    path(
        "update_regional_timeline/",
        views.update_regional_timeline,
        name="update_regional_timeline",
    ),
    path(
        "update_national_timeline/",
        views.update_national_timeline,
        name="update_national_timeline",
    ),
    path(
        "update_thematic_area_comments/",
        views.update_thematic_area_comments,
        name="update_thematic_area_comments",
    ),
    path("District_login/", views.place_login, name="place_login"),
    path("trends/", views.activity_trend, name="activity_trend"),
    path(
        "district_trends/", views.district_participation_trend, name="district_trends"
    ),
    path("trend_selection/", views.trend_selection, name="trend_selection"),
    path("api/places/", views.get_places_by_region, name="get_places_by_region"),
    path(
        "regional_activity_trend/",
        views.regional_activity_trend,
        name="regional_activity_trend",
    ),
    path(
        "regional_district_participation_trend/",
        views.regional_district_participation_trend,
        name="regional_district_participation_trend",
    ),
    path(
        "regional_trend_selection/",
        views.regional_trend_selection,
        name="regional_trend_selection",
    ),
    path(
        "regional/manage_places/",
        views.regional_manage_places,
        name="regional_manage_places",
    ),
    path(
        "regional/add_place_user/<int:place_id>/",
        views.regional_assign_place_user,
        name="regional_assign_place_user",
    ),
    path(
        "regional/delete_place_user/<int:user_id>/",
        views.regional_delete_place_user,
        name="regional_delete_place_user",
    ),
    path("national_users/", views.manage_national_users, name="manage_national_users"),
    path(
        "create_national_user/", views.create_national_user, name="create_national_user"
    ),
    path(
        "district_readiness/",
        views.readiness_analysis_view,
        name="readiness_analysis_view",
    ),
    path("overall_readiness/", views.combined_dashboard, name="combined_dashboard"),
    path("Readiness/pdf/", views.combined_dashboard_pdf, name="dashboard_pdf"),
    path(
        "readiness-analysis/pdf/",
        views.readiness_analysis_pdf,
        name="readiness_analysis_pdf",
    ),
    path(
        "export_csv_place/<int:place_id>/",
        views.export_csv_place,
        name="export_csv_place",
    ),
]
