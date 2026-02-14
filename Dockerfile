# Use the Official ERPNext v15 Image
# ERPNext and Frappe are pre-installed in this image
FROM frappe/erpnext:v15

USER root

COPY --chown=frappe:frappe scripts/ /opt/erp-deploy/scripts/
RUN chmod 0755 /opt/erp-deploy/scripts/*.sh

# Ship custom apps inside the image so they persist across redeploys.
COPY --chown=frappe:frappe apps/custom_desk_theme/ /home/frappe/frappe-bench/apps/custom_desk_theme/
COPY --chown=frappe:frappe apps/orderlift/ /home/frappe/frappe-bench/apps/orderlift/

# Install the custom apps so they're importable by Python
RUN pip install -e /home/frappe/frappe-bench/apps/custom_desk_theme/
RUN pip install -e /home/frappe/frappe-bench/apps/orderlift/

# Switch to the frappe user (Security Requirement)
USER frappe

# Pre-fetch HRMS app code so it persists across redeploys.
# Site installation and migrations are handled by create-site.sh.
WORKDIR /home/frappe/frappe-bench
RUN bench get-app --branch version-15 --skip-assets hrms https://github.com/frappe/hrms.git

# Build assets for all apps including HRMS.
# This ensures CSS/JS bundles exist and are fingerprinted correctly.
RUN bench build

# Expose ports so reverse proxies can auto-detect.
EXPOSE 8000 8080 9000
