# Use the Official ERPNext v15 Image
# ERPNext and Frappe are pre-installed in this image
FROM frappe/erpnext:v15

USER root

COPY --chown=frappe:frappe scripts/ /opt/erp-deploy/scripts/
RUN chmod 0755 /opt/erp-deploy/scripts/*.sh

# Switch to the frappe user (Security Requirement)
USER frappe

WORKDIR /home/frappe/frappe-bench

# Pre-fetch HRMS app code so it persists across redeploys.
# Site installation and migrations are handled by create-site.sh.
RUN bench get-app --branch version-15 --skip-assets hrms https://github.com/frappe/hrms.git

# Create a dummy common_site_config.json for the build step
# HRMS frontend build fails if this file (and socketio_port) is missing
RUN echo '{"socketio_port": 9000}' > /home/frappe/frappe-bench/sites/common_site_config.json

# Build assets for all apps including HRMS.
# This ensures CSS/JS bundles exist and are fingerprinted correctly.
RUN bench build

# Back up the built assets so they can be restored to the volume at runtime
# Copy to a location OUTSIDE the sites volume
RUN cp -r /home/frappe/frappe-bench/sites/assets /home/frappe/frappe-bench/assets-backup

# Expose ports so reverse proxies can auto-detect.
EXPOSE 8000 8080 9000
