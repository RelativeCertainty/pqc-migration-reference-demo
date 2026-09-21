from __future__ import annotations

from .venafi_common import VenafiCertificateSearchAdapterBase


class VenafiCertificateManagerAdapter(VenafiCertificateSearchAdapterBase):
    """CyberArk Certificate Manager SaaS / legacy Venafi search dialect."""

    adapter_id = "venafi-certificate-manager-saas-v1"
    pack_id = "venafi-certificate-manager-saas-v1"
    provider = "venafi"
    product = "certificate_manager_saas"
    dialect = "certificate_manager_outagedetection_v1"
