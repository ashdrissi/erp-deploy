# 1. Use the Official ERPNext v15 Image
FROM frappe/erpnext:v15.0.0

# 2. Switch to the frappe user (Security Requirement)
USER frappe

# 3. Install a Real Custom App (Example: HRMS)
# -------------------------------------------------------------------------
# 👇 REPLACE THE LINK BELOW WITH YOUR GIT REPO URL
#    If your repo is private, use: https://token@github.com/username/repo.git
RUN bench get-app https://github.com/frappe/hrms.git
# -------------------------------------------------------------------------

# 4. Build the assets (CSS/JS)
#    This compiles the code from ERPNext AND your custom app together.
RUN bench build
