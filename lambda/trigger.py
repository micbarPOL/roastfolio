"""
lambda/trigger.py — Cognito PostConfirmation Lambda trigger

Invoked by Cognito synchronously after a user confirms their email.
Creates the DynamoDB user profile if it doesn't already exist.

Trigger source handled:  PostConfirmation_ConfirmSignUp
Other sources (admin create, forgot-password confirm) are skipped.

Idempotency: db.create_user uses attribute_not_exists(userId) so
calling this twice for the same user is safe — the second call is
a no-op (ConditionalCheckFailedException is swallowed).

Timeout budget: Cognito gives the trigger ~5 s before it fails the
confirmation.  DynamoDB PutItem typically takes < 20 ms, so there
is plenty of headroom.  We set the SAM timeout to 10 s as a guard.
"""

import json
import logging
import os

import db  # shared DynamoDB helpers in the same Lambda package

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context) -> dict:
    """
    Cognito PostConfirmation trigger entry point.

    Event shape (Cognito):
    {
        "version": "1",
        "triggerSource": "PostConfirmation_ConfirmSignUp",
        "region": "us-west-2",
        "userPoolId": "us-west-2_XXXXXXX",
        "userName": "a1b2c3d4-...",          ← Cognito sub (used as userId)
        "request": {
            "userAttributes": {
                "sub":              "a1b2c3d4-...",
                "email":            "user@example.com",
                "email_verified":   "true",
                "nickname":         "WarrenFromWarsaw",
                "cognito:user_status": "CONFIRMED"
            }
        },
        "response": {}
    }

    Must return the event unchanged — Cognito ignores the response
    body but will fail the confirmation if an exception is raised.
    """
    trigger_source = event.get("triggerSource", "")
    logger.info("Trigger source: %s", trigger_source)

    # Only handle email-confirmation signups.
    # PostConfirmation_ConfirmForgotPassword fires on password resets
    # and does NOT need a profile (user already has one).
    if trigger_source != "PostConfirmation_ConfirmSignUp":
        logger.info("Skipping non-signup trigger source.")
        return event

    attrs     = event.get("request", {}).get("userAttributes", {})
    user_id   = attrs.get("sub", "").strip()
    email     = attrs.get("email", "").strip().lower()
    nickname  = attrs.get("nickname", "").strip()

    # Fallback: use the part before @ as a nickname if Cognito didn't supply one
    if not nickname and email:
        nickname = email.split("@")[0]

    if not user_id or not email:
        # Should never happen — log and let Cognito proceed
        logger.error(
            "Missing required attributes. sub=%r email=%r — skipping profile creation.",
            user_id, email
        )
        return event

    logger.info("Creating profile for userId=%s email=%s", user_id, email)

    try:
        profile = db.create_user(user_id, email, nickname)
        logger.info(
            "Profile created. userId=%s createdAt=%s",
            profile["userId"], profile["createdAt"]
        )
    except Exception as e:
        # ConditionalCheckFailedException → profile already exists (idempotent)
        error_name = type(e).__name__
        if "ConditionalCheckFailed" in error_name:
            logger.info("Profile already exists for userId=%s — skipping.", user_id)
        else:
            # Log the error but DO NOT re-raise.
            # Re-raising would cause Cognito to mark the confirmation as failed,
            # leaving the user in a broken state (confirmed in Cognito but getting
            # an error on screen).  It is better to let the confirmation succeed
            # and create the profile lazily on the first /profile GET instead.
            logger.error(
                "Unexpected error creating profile for userId=%s: %s — %s",
                user_id, error_name, e
            )

    # Cognito requires the event to be returned unchanged
    return event
