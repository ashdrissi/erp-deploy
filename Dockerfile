# Use the Official ERPNext v15 Image
# ERPNext and Frappe are pre-installed in this image
FROM frappe/erpnext:v15

USER root

COPY --chown=frappe:frappe scripts/ /opt/erp-deploy/scripts/
RUN chmod 0755 /opt/erp-deploy/scripts/*.sh

# Switch to the frappe user (Security Requirement)
USER frappe

# NOTE: Custom apps (like HRMS) should be installed AFTER deployment
# using the bench command inside the running container:
#   bench get-app hrms
#   bench --site $SITE_NAME install-app hrms
#   bench build

# Expose ports so reverse proxies can auto-detect.
EXPOSE 8000 8080 9000
