from django.core.exceptions import PermissionDenied

from wagtail.log_actions import log

# ConvertAlias (usually seen as ConvertAliasPageAction or similar) is an action that turns an alias page into a normal page.
# A normal page is independent; its content is stored directly in the database.
# An alias page is a “reference” to another page.
# It displays the same content as the original page.
# Editing an alias does not change the original page (in some contexts, it might be blocked).
# An alias page is a “mirror” of another page.
# It shares the content of the original page (alias_of_id points to the original).
# Editing the alias directly is restricted or may affect multiple places (depending on Wagtail’s settings).

class ConvertAliasPageError(RuntimeError):
    """
    Raised when the page to convert is not an alias.
    """

    pass


class ConvertAliasPagePermissionError(PermissionDenied):
    """
    Raised when the alias page conversion cannot be performed due to insufficient permissions.
    """

    pass


class ConvertAliasPageAction:
    def __init__(self, page, *, log_action="wagtail.convert_alias", user=None):
        self.page = page
        self.log_action = log_action
        self.user = user

    def check(self, skip_permission_checks=False):
        if not self.page.alias_of_id:
            raise ConvertAliasPageError("Page must be an alias to be converted.")

        if (
            not skip_permission_checks
            and self.user
            and not self.page.permissions_for_user(self.user).can_edit()
        ):
            raise ConvertAliasPagePermissionError(
                "You do not have permission to edit this page."
            )

    def _convert_alias(self, page, log_action, user):
        # Break the alias
        page.alias_of_id = None
        page.save(update_fields=["alias_of_id"], clean=False)

        # Create an initial revision
        revision = page.save_revision(user=user, changed=False, clean=False)

        # Update live revision if page is published
        if page.live:
            page.live_revision = revision
            page.save(update_fields=["live_revision"], clean=False)

        # Log the action
        if log_action:
            log(
                instance=page,
                action=log_action,
                revision=revision,
                user=user,
                data={
                    "page": {"id": page.id, "title": page.get_admin_display_title()},
                },
            )

        return page

    # check and then convert
    def execute(self, skip_permission_checks=False):
        self.check(skip_permission_checks=skip_permission_checks)

        return self._convert_alias(self.page, self.log_action, self.user)
