from django.urls import path

from . import views

app_name = "companies"
urlpatterns = [
    path("nouveau/", views.onboarding, name="onboarding"),
    path("selection/", views.select_company, name="select"),
    path("gestion/", views.company_list, name="list"),
    path("gestion/<uuid:company_id>/modifier/", views.company_edit, name="edit"),
    path("gestion/<uuid:company_id>/statut/", views.company_status, name="status"),
    path("equipe/", views.team, name="team"),
    path("equipe/inviter/", views.invite_member, name="team-invite"),
    path("equipe/invitations/<uuid:invitation_id>/revoquer/", views.revoke_invitation, name="invitation-revoke"),
    path("equipe/invitations/<uuid:invitation_id>/renvoyer/", views.resend_invitation, name="invitation-resend"),
    path("equipe/membres/<uuid:membership_id>/modifier/", views.member_edit, name="member-edit"),
    path("equipe/membres/<uuid:membership_id>/acces/", views.member_access, name="member-access"),
    path("invitations/<str:token>/accepter/", views.accept_invitation, name="invitation-accept"),
]
