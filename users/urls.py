from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from users import views
from core.settings import PATH_BASE

BASE_PATH_USERS = f"{PATH_BASE}users/"

login_user = views.AuthenticationViewSet.as_view({"post": "login"})
logout_user = views.AuthenticationViewSet.as_view({"get": "logout"})
refresh_token = views.AuthenticationViewSet.as_view({"get": "refresh"})

get_menu_options = views.MenuOptionsViewSet.as_view({"get": "get_menu_options"})

get_list_users = views.UserViewSet.as_view({"post": "get_list_users"})
get_user = views.UserViewSet.as_view({"post": "get_user"})
create_user = views.UserViewSet.as_view({"post": "create_user"})
change_state = views.UserViewSet.as_view({"put": "change_state"})
update_user = views.UserViewSet.as_view({"put": "update_user"})
change_user_rol = views.UserViewSet.as_view({"put": "change_user_rol"})
asign_role = views.UserViewSet.as_view({"post": "asign_role"})
remove_role = views.UserViewSet.as_view({"put": "remove_role"})
get_roles_list = views.UserViewSet.as_view({"post": "get_roles_list"})
change_password = views.UserViewSet.as_view({"put": "change_password"})
get_department_list = views.UserViewSet.as_view({"post": "get_department_list"})
check_username = views.UserViewSet.as_view({"post": "check_username"})
check_identity_document = views.UserViewSet.as_view({"post": "check_identity_document"})
update_avatar = views.UserViewSet.as_view({"put": "update_avatar"})


urlpatterns = [
    path(f"{BASE_PATH_USERS}login/", login_user),
    path(f"{BASE_PATH_USERS}logout/", logout_user),
    path(f"{BASE_PATH_USERS}refresh/", refresh_token),
    path(f"{BASE_PATH_USERS}change_password/", change_password),
    path(f"{BASE_PATH_USERS}menu_options/", get_menu_options),
    path(f"{BASE_PATH_USERS}list_users", get_list_users),
    path(f"{BASE_PATH_USERS}get_user/", get_user),
    path(f"{BASE_PATH_USERS}create_user/", create_user),
    path(f"{BASE_PATH_USERS}change_user_state/", change_state),
    path(f"{BASE_PATH_USERS}update_user/", update_user),
    path(f"{BASE_PATH_USERS}change_user_rol/", change_user_rol),
    path(f"{BASE_PATH_USERS}asign_role/", asign_role),
    path(f"{BASE_PATH_USERS}remove_role/", remove_role),
    path(f"{BASE_PATH_USERS}get_roles_list", get_roles_list),
    path(f"{BASE_PATH_USERS}get_department_list/", get_department_list),
    path(f"{BASE_PATH_USERS}check_username/", check_username),
    path(f"{BASE_PATH_USERS}check_identity_document/", check_identity_document),
    path(f"{BASE_PATH_USERS}update_avatar/", update_avatar),
]

urlpatterns = format_suffix_patterns(urlpatterns)
