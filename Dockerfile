# Use the Official ERPNext v15 Image
# ERPNext and Frappe are pre-installed in this image
FROM frappe/erpnext:v15

USER root

COPY --chown=frappe:frappe scripts/ /opt/erp-deploy/scripts/
RUN chmod 0755 /opt/erp-deploy/scripts/*.sh

# Switch to the frappe user (Security Requirement)
USER frappe

# Pre-fetch HRMS app code so it persists across redeploys.
# Site installation and migrations are handled by create-site.sh.
WORKDIR /home/frappe/frappe-bench
RUN bench get-app --branch version-15 --skip-assets hrms https://github.com/frappe/hrms.git

# Expose ports so reverse proxies can auto-detect.
EXPOSE 8000 8080 9000
