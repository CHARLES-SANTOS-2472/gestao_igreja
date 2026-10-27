from .access import can_manage_users


def user_management(request):
    return {"can_manage_users": can_manage_users(request.user)}
