Implementation Plan: Shout App Task Expiration & Account Deletion
Overview
The user requested to:

Enable the worker's Accepted Tasks Dashboard to show tasks that have expired (with an "Expired" status badge and banner), instead of disappearing or showing inaccurate status.
Ensure that when a campaign or its advertiser is removed/cancelled, worker submissions transition to status = 'expired' rather than being deleted, so every worker who accepted the task sees it marked as Expired on their Accepted dashboard.
Access EASYEASY PROD on Railway Postgres to:
Transition all active/pending submissions on Campaign 29 ("Download the Shout app from App store or Playstore") to expired.
Cancel/remove Campaign 29 and clean up User 1000's account and connected records.
Commit and test all code changes on branch staging, push to origin/staging, then merge into main and push to origin/main.
User Review Required
IMPORTANT

Production Cleanup Details:

Campaign ID: 29 ("Download the Shout app from App store or Playstore")
Advertiser ID: 1000 (Ayuk Ndi Parreyntoh, ayukndiparreyntoh@gmail.com)
Workers affected: 7 currently accepted submissions (IDs: 141, 144, 140, 129, 130, 132, 135).
Action on Submissions: Their status will be set to status = 'expired' with expired_at = CURRENT_TIMESTAMP and reason "This task was closed by the creator.". They will immediately see this task marked as Expired under their Accepted tasks tab in the mobile app.
Action on Campaign: Set status = 'cancelled', accepted_slots = 0.
Action on User 1000: Purge notifications, payments, withdrawals, and delete the user row as requested.
Proposed Changes
1. Mobile App (Easyeasy-Mobile-App)
[MODIFY] 
TaskRoomScreen.tsx
Under activeFilter === "accepted":
Include both s.status === "accepted" AND s.status === "expired".
Mark type: s.status === "expired" ? "Expired" : "To Do".
In the task card status pill:
Add explicit styling for task.status === "expired" (danger red badge: "Expired" with alert icon).
In the task detail modal / action view:
When task.status === "expired":
Display an alert banner: "This task has expired or was closed by the creator. Proof can no longer be submitted."
Disable or hide the "Submit Proof" button for expired tasks.
2. Backend (EASYEASY-AI)
[MODIFY] 
user_cleanup_service.py
When cleaning up an advertiser's campaigns:
Instead of hard-deleting the active worker submissions, update all submissions with status in ['accepted', 'pending'] to:
status = 'expired'
expired_at = datetime.utcnow()
rejection_reason = 'This task was closed by the creator.'
Update campaign.status = 'cancelled' and campaign.accepted_slots = 0.
This ensures the campaign is removed from the public available task feed, while workers who accepted it keep their submission record marked as Expired.
[MODIFY] 
api_v2.py
In get_task_analytics() (/v2/analytics/dashboard):
In worker_stats, include "expired": sum(1 for s in my_submissions if s.status == 'expired').
3. Production Database Update (Railway Postgres)
Run a script to:

Transition all 7 active submissions for Campaign 29 to expired:
sql

UPDATE task_submissions 
SET status = 'expired', 
    expired_at = CURRENT_TIMESTAMP, 
    rejection_reason = 'This task was closed by the creator.' 
WHERE campaign_id = 29 AND status IN ('accepted', 'pending');
Update Campaign 29 to cancelled:
sql

UPDATE task_campaigns 
SET status = 'cancelled', accepted_slots = 0 
WHERE id = 29;
Purge user 1000's connected data and delete user 1000:
sql

DELETE FROM app_notifications WHERE user_id = 1000;
DELETE FROM payments WHERE user_id = 1000;
DELETE FROM withdrawals WHERE user_id = 1000;
DELETE FROM users WHERE id = 1000;
4. Git Deployment
In Easyeasy-Mobile-App: Commit changes to staging, push to origin/staging, merge into main, push to origin/main.
In EASYEASY-AI: Commit changes to staging, push to origin/staging, merge into main, push to origin/main.
Verification Plan
Automated / Syntax Tests
Run python3 -m py_compile on backend files.
Run npx tsc --noEmit on Easyeasy-Mobile-App.
Run database verification queries on Railway Prod to confirm:
Campaign 29 is cancelled.
All 7 workers' submissions now have status = 'expired'.
User 1000 is deleted.
No active campaigns exist for Shout app.
Manual Verification
Verify via API and database that workers with submissions for campaign 29 receive status: 'expired' with rejection explanation.
