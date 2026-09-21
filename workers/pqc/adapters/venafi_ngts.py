from __future__ import annotations

from .venafi_common import VenafiCertificateSearchAdapterBase


class VenafiNGTSAdapter(VenafiCertificateSearchAdapterBase):
    """Palo Alto Networks Next-Gen Trust Security certificate-search dialect."""

    adapter_id = "venafi-ngts-outagedetection-v1"
    pack_id = "venafi-ngts-outagedetection-v1"
    provider = "palo_alto_networks"
    product = "next_gen_trust_security"
    dialect = "ngts_outagedetection_v1"
