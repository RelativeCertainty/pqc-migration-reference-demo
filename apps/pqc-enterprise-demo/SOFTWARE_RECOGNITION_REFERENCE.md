# PQC Discovery Domains — software recognition reference

242 examples across 10 discovery domains and 27 software classes. Reference version: pqc.software-recognition.v1. Reviewed: September 10, 2026.

Use these names to recognize a software class and identify the right products or teams. They are not a complete market inventory, a confirmed enterprise stack, purchasing recommendations, PQC-readiness claims or qualified connectors. An unlisted product or a referral is equally useful. Several products and deployments may serve the same function.

COTS means commercial off-the-shelf; OTS means off-the-shelf; SaaS means software as a service. Open-source and relevant hardware/platform examples are included. Offering labels are broad recognition categories, not exact licensing or deployment profiles. Follow the official product references; installed versions and permitted interfaces still require confirmation.

## 1. Enterprise context

### Application portfolio

- [SAP LeanIX Application Portfolio Management](https://www.leanix.net/en/products/application-portfolio-management) (SaaS) — Application inventory and portfolio analysis.
- [ServiceNow Enterprise Architecture](https://www.servicenow.com/products/enterprise-architecture.html) (SaaS) — Enterprise architecture and application portfolio context.
- [Bizzdesign Alfabet](https://bizzdesign.com/transformation-suite/alfabet) (SaaS) — IT portfolio planning and application relationships.
- [Bizzdesign Horizzon](https://bizzdesign.com/transformation-suite/horizzon) (SaaS) — Enterprise architecture models and relationships.
- [Bizzdesign Hopex](https://bizzdesign.com/transformation-suite/hopex) (SaaS) — Architecture and application portfolio context.
- [OrbusInfinity](https://www.orbussoftware.com/product/orbusinfinity) (SaaS) — Orbus Software enterprise architecture platform.
- [Ardoq](https://www.ardoq.com/) (SaaS) — Application portfolios and architecture relationships.
- [Essential Open Source](https://enterprise-architecture.org/products/essential-open-source/) (Open source) — The Essential Project; application and architecture repository.

### CMDB and asset inventory

- [ServiceNow Configuration Management Database](https://www.servicenow.com/products/servicenow-platform/configuration-management-database.html) (SaaS) — ServiceNow CMDB; configuration items and relationships.
- [BMC Helix CMDB](https://www.helixops.ai/products/bmc-helix-cmdb.html) (COTS) — Configuration data and service relationships.
- [Jira Service Management Assets](https://www.atlassian.com/software/jira/service-management/features/asset-and-configuration-management) (SaaS) — Atlassian asset and configuration management.
- [Device42](https://www.device42.com/) (COTS) — Discovery, asset inventory, and dependency mapping.
- [OpenText Universal Discovery and CMDB](https://www.opentext.com/products/universal-discovery-and-cmdb) (COTS) — Universal CMDB / UCMDB recognition context.
- [iTop](https://combodo.com/) (Open source) — Combodo service management and CMDB.
- [CMDBuild](https://www.cmdbuild.org/en) (Open source) — Configurable asset and configuration database.
- [GLPI](https://www.glpi-project.org/en/) (Open source) — IT inventory, assets, and service management.

## 2. PKI and trust

### Certificate authorities

- [Microsoft Active Directory Certificate Services](https://learn.microsoft.com/en-us/windows-server/identity/ad-cs/active-directory-certificate-services-overview) (COTS) — AD CS; Windows Server certificate authority roles.
- [EJBCA Community](https://www.ejbca.org/) (Open source) — Certificate authority software; EJBCA Enterprise is a separate edition.
- [Dogtag Certificate System](https://www.dogtagpki.org/) (Open source) — Dogtag PKI; certificate authority software.
- [Smallstep step-ca](https://smallstep.com/docs/step-ca/) (Open source) — Step CA; private certificate authority server.
- [OpenXPKI](https://www.openxpki.org/) (Open source) — PKI and trust-center software.
- [AWS Private Certificate Authority](https://aws.amazon.com/private-ca/) (SaaS) — AWS Private CA; managed private certificate issuance.
- [Google Cloud Certificate Authority Service](https://cloud.google.com/security/products/certificate-authority-service) (SaaS) — Managed private certificate authority service.
- [HashiCorp Vault PKI secrets engine](https://developer.hashicorp.com/vault/docs/secrets/pki) (COTS) — Vault component for issuing and managing certificates.

### Certificate lifecycle management

- [Keyfactor Command](https://www.keyfactor.com/products/command/) (COTS) — Certificate inventory and lifecycle automation.
- [CyberArk Certificate Manager, Self-Hosted](https://www.cyberark.com/resources/product-datasheets/cyberark-certificate-manager-self-hosted) (COTS) — Recognition alias: Venafi TLS Protect.
- [DigiCert Trust Lifecycle Manager](https://www.digicert.com/trust-lifecycle-manager) (SaaS) — Certificate discovery, inventory, and lifecycle management.
- [AppViewX CERT+](https://www.appviewx.com/solutions/certificate-lifecycle-management/) (COTS) — Certificate lifecycle management; also labeled CLM.
- [Sectigo Certificate Manager](https://www.sectigo.com/enterprise-solutions/certificate-manager) (SaaS) — SCM; certificate lifecycle management.
- [cert-manager](https://cert-manager.io/) (Open source) — Kubernetes certificate issuance and renewal controller.
- [Certbot](https://certbot.eff.org/) (Open source) — ACME client for certificate issuance and renewal.
- [AWS Certificate Manager](https://aws.amazon.com/certificate-manager/) (SaaS) — ACM; managed certificate provisioning and renewal.
- [Azure Key Vault certificates](https://learn.microsoft.com/en-us/azure/key-vault/certificates/about-certificates) (SaaS) — Certificate objects, policies, and lifecycle management.

### Hardware security modules and services

- [Thales Luna Network HSM](https://cpl.thalesgroup.com/encryption/hardware-security-modules/network-hsms) (Hardware/platform) — Physical network HSM appliance; not application software.
- [Entrust nShield Connect](https://www.entrust.com/products/hsm/nshield-connect) (Hardware/platform) — Physical network HSM appliance; not application software.
- [Utimaco u.trust General Purpose HSM Se-Series](https://utimaco.com/products/categories/hsms-general-purpose-use-cases/securityserver) (Hardware/platform) — Hardware HSM family; SecurityServer / CryptoServer recognition context.
- [IBM 4769 Cryptographic Coprocessor](https://www.ibm.com/docs/en/cryptocards?topic=4769-overview) (Hardware/platform) — PCIe hardware HSM; CEX7S / 4769.
- [Marvell LiquidSecurity 2 HSM Adapter](https://www.marvell.com/products/security-solutions/liquidsecurity2.html) (Hardware/platform) — LS2; hardware HSM adapter card.
- [Yubico YubiHSM 2](https://www.yubico.com/products/hardware-security-module/) (Hardware/platform) — USB hardware HSM; distinct from YubiKey authenticators.
- [AWS CloudHSM](https://aws.amazon.com/cloudhsm/) (Hardware/platform) — Managed cloud HSM service backed by hardware.
- [Azure Key Vault Managed HSM](https://learn.microsoft.com/en-us/azure/key-vault/managed-hsm/overview) (Hardware/platform) — Managed cloud HSM service backed by hardware.

## 3. Encrypted traffic

### API gateways and service mesh

- [Istio](https://istio.io/) (Open source) — Service mesh for service-to-service communication.
- [Linkerd](https://linkerd.io/) (Open source) — Kubernetes service mesh.
- [HashiCorp Consul](https://developer.hashicorp.com/consul/docs) (COTS) — Service discovery and service mesh.
- [Envoy Proxy](https://www.envoyproxy.io/) (Open source) — Edge and service proxy.
- [Kong Gateway](https://developer.konghq.com/gateway/) (COTS) — API gateway; open-source edition also exists.
- [Apache APISIX](https://apisix.apache.org/) (Open source) — API gateway.
- [Tyk Gateway OSS](https://tyk.io/docs/tyk-oss-gateway) (Open source) — Open-source API gateway edition.
- [WSO2 API Manager](https://apim.docs.wso2.com/en/latest/) (Open source) — API management and gateway software.

### Network telemetry and analysis

- [Wireshark](https://www.wireshark.org/) (Open source) — Packet capture and protocol analysis.
- [Zeek](https://zeek.org/) (Open source) — Network security monitor; recognition alias: Bro.
- [Suricata](https://suricata.io/) (Open source) — Network traffic analysis and threat detection.
- [ntopng](https://www.ntop.org/products/traffic-analysis/ntopng/) (Open source) — Community traffic-analysis software; commercial editions also exist.
- [Arkime](https://arkime.com/) (Open source) — Packet capture indexing and session analysis.
- [Corelight Software Sensor](https://corelight.com/platform/sensors) (COTS) — Software sensor for Linux and Kubernetes environments.
- [ExtraHop RevealX](https://www.extrahop.com/platform) (COTS) — Network detection and response platform.
- [Cisco Secure Network Analytics](https://www.cisco.com/c/en/us/products/collateral/security/stealthwatch/datasheet-c78-739398.html) (COTS) — Stealthwatch; virtual software deployment is one form.

### Traffic termination and reverse proxies

- [NGINX Open Source](https://nginx.org/) (Open source) — Web server and reverse proxy.
- [HAProxy](https://www.haproxy.org/) (Open source) — TCP/HTTP load balancer and proxy.
- [Apache HTTP Server](https://httpd.apache.org/) (Open source) — httpd; web server with TLS modules.
- [Caddy](https://caddyserver.com/) (Open source) — Web server and reverse proxy with automatic HTTPS.
- [Traefik Proxy](https://traefik.io/traefik) (Open source) — Application proxy and ingress routing.
- [F5 BIG-IP Local Traffic Manager Virtual Edition](https://www.f5.com/trials/big-ip-virtual-edition) (COTS) — BIG-IP LTM VE; virtual traffic-management software.
- [NetScaler VPX](https://www.netscaler.com/platform/vpx-virtual-machine) (COTS) — Virtual application delivery controller software.
- [AWS Application Load Balancer](https://aws.amazon.com/elasticloadbalancing/application-load-balancer/) (SaaS) — ALB; managed application traffic termination.
- [Azure Application Gateway](https://learn.microsoft.com/en-us/azure/application-gateway/overview) (SaaS) — Managed application load balancing and TLS termination.
- [Google Cloud Load Balancing](https://docs.cloud.google.com/load-balancing/docs/load-balancing-overview) (SaaS) — Managed load balancer family; termination depends on type.

## 4. Machine access

### SSH and secure machine access

- [OpenSSH](https://www.openssh.org/) (Open source) — SSH clients and servers; ssh, sshd, scp, and sftp.
- [PuTTY](https://www.chiark.greenend.org.uk/~sgtatham/putty/) (Open source) — SSH client suite for Windows and other systems.
- [Dropbear SSH](https://matt.ucc.asn.au/dropbear/dropbear.html) (Open source) — Small SSH server and client, including embedded systems.
- [Bitvise SSH Server](https://bitvise.com/ssh-server) (COTS) — SSH and SFTP server for Windows.
- [VanDyke VShell](https://www.vandyke.com/products/vshell/) (COTS) — SSH-based secure file-transfer server.
- [VanDyke SecureCRT](https://www.vandyke.com/products/securecrt/) (COTS) — SSH terminal client.
- [Teleport](https://goteleport.com/docs/enroll-resources/server-access/) (COTS) — Server access through SSH and certificate-based identity.
- [WinSCP](https://winscp.net/eng/index.php) (Open source) — Windows SFTP/SCP client using SSH.
- [Tectia SSH](https://www.ssh.com/products/tectia-ssh/) (COTS) — SSH Communications Security client/server software.
- [CyberArk SSH Manager for Machines](https://docs.venafi.com/Docs/current/TopNav/Content/Release-Documents/important_considerations.php?TocPath=Platform%7CRelease+Documents%7C_____2) (COTS) — Recognition alias: Venafi SSH Protect.

### VPN and remote network access

- [OpenVPN Community Edition](https://openvpn.net/community/) (Open source) — OpenVPN open-source VPN software.
- [WireGuard](https://www.wireguard.com/) (Open source) — VPN tunnel software.
- [strongSwan](https://www.strongswan.org/) (Open source) — IPsec and IKE VPN implementation.
- [SoftEther VPN](https://www.softether.org/) (Open source) — Multi-protocol VPN client and server.
- [OpenConnect](https://www.infradead.org/openconnect/) (Open source) — Multi-protocol VPN client.
- [Cisco Secure Client](https://www.cisco.com/site/us/en/products/security/secure-client/index.html) (COTS) — Includes the AnyConnect VPN client.
- [Palo Alto Networks GlobalProtect](https://www.paloaltonetworks.com/sase/globalprotect) (COTS) — Remote access client and gateway ecosystem.
- [Fortinet FortiClient](https://www.fortinet.com/products/endpoint-security/forticlient) (COTS) — Endpoint agent including VPN and remote-access functions.
- [Ivanti Secure Access Client](https://www.ivanti.com/products/secure-access-client) (COTS) — Endpoint client for secure remote access.
- [Tailscale](https://tailscale.com/) (SaaS) — Managed connectivity service with device clients.

## 5. Software delivery

### Dependency and component analysis

- [Syft](https://github.com/anchore/syft) (Open source) — Anchore tool for software bill of materials generation.
- [Trivy](https://trivy.dev/) (Open source) — Artifact, dependency, and container security scanner.
- [OWASP Dependency-Check](https://dependency-check.github.io/DependencyCheck/) (Open source) — Dependency analysis for known vulnerable components.
- [OWASP Dependency-Track](https://dependencytrack.org/) (Open source) — SBOM-based component inventory and analysis.
- [Snyk Open Source](https://snyk.io/product/open-source-security-management/) (SaaS) — Commercial software composition analysis service.
- [Mend SCA](https://www.mend.io/sca/) (SaaS) — Software composition analysis.
- [Sonatype Lifecycle](https://www.sonatype.com/products/open-source-security-dependency-management) (COTS) — Dependency and software composition analysis.
- [Black Duck SCA](https://www.blackduck.com/software-composition-analysis-tools.html) (COTS) — Software composition analysis and component identification.

### Software and artifact signing

- [Sigstore Cosign](https://docs.sigstore.dev/cosign/signing/overview/) (Open source) — Artifact signing and signature verification.
- [SignServer Community](https://www.signserver.org/) (Open source) — Server-side code and artifact signing.
- [GnuPG](https://gnupg.org/) (Open source) — GNU Privacy Guard; OpenPGP signatures.
- [Microsoft SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool) (COTS) — Windows SDK command-line signing and verification tool.
- [DigiCert Software Trust Manager](https://www.digicert.com/software-trust-manager) (SaaS) — Software signing and signing-key management.
- [Microsoft Artifact Signing](https://learn.microsoft.com/en-us/azure/artifact-signing/overview) (SaaS) — Managed code-signing service in Azure.
- [AWS Signer](https://docs.aws.amazon.com/signer/) (SaaS) — Managed code-signing service.
- [Jsign](https://ebourg.github.io/jsign/) (Open source) — Authenticode signing tool for Windows artifacts.
- [osslsigncode](https://github.com/mtrojnar/osslsigncode) (Open source) — OpenSSL-based Authenticode signing utility.
- [CyberArk Code Sign Manager](https://docs.venafi.com/Docs/current/TopNav/Content/Release-Documents/important_considerations.php?TocPath=Platform%7CRelease+Documents%7C_____2) (COTS) — Recognition alias: Venafi CodeSign Protect.

### Source control and build systems

- [GitHub Enterprise Cloud](https://docs.github.com/en/enterprise-cloud@latest/admin/overview/about-github-enterprise-cloud) (SaaS) — Hosted source control and developer platform.
- [GitLab Self-Managed](https://docs.gitlab.com/user/project/repository/) (COTS) — Source repositories and CI/CD; self-managed distribution.
- [Jenkins](https://www.jenkins.io/) (Open source) — Automation server for build and delivery jobs.
- [JetBrains TeamCity](https://www.jetbrains.com/teamcity/) (COTS) — Continuous integration and delivery server.
- [Azure DevOps Services](https://learn.microsoft.com/en-us/azure/devops/user-guide/what-is-azure-devops?view=azure-devops) (SaaS) — Includes Azure Repos and Azure Pipelines.
- [Atlassian Bamboo](https://www.atlassian.com/software/bamboo) (COTS) — Continuous integration and deployment server.
- [CircleCI](https://circleci.com/) (SaaS) — Continuous integration and delivery service.
- [Buildkite Pipelines](https://buildkite.com/home/) (SaaS) — Pipeline orchestration with hosted or self-hosted agents.

## 6. Cloud, keys and identity

### Cloud workloads and runtime inventory

- [AWS Config](https://docs.aws.amazon.com/config/latest/developerguide/WhatIsConfig.html) (SaaS) — AWS resource configuration inventory and history.
- [Azure Resource Graph](https://learn.microsoft.com/en-us/azure/governance/resource-graph/overview) (SaaS) — Queries resource metadata across Azure subscriptions.
- [Google Cloud Asset Inventory](https://docs.cloud.google.com/asset-inventory/docs/asset-inventory-overview) (SaaS) — Google Cloud resource and policy metadata inventory.
- [Oracle Cloud Infrastructure Search](https://docs.oracle.com/en-us/iaas/Content/Search/Concepts/queryoverview.htm) (SaaS) — OCI Search; locates cloud resources by their attributes.
- [Kubernetes](https://kubernetes.io/docs/concepts/overview/) (Open source) — Container orchestration platform; cluster objects describe workloads.
- [Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift) (COTS) — Enterprise application and Kubernetes platform.
- [Nutanix Prism](https://www.nutanix.com/products/prism) (COTS) — Management software for Nutanix infrastructure and workloads.
- [OpenStack](https://www.openstack.org/software/) (Open source) — Cloud infrastructure software; deployments include multiple services.
- [CloudQuery](https://www.cloudquery.io/) (SaaS) — Cloud asset inventory and configuration data platform.

### Identity and access management

- [Microsoft Entra ID](https://learn.microsoft.com/en-us/entra/fundamentals/new-name) (SaaS) — Cloud identity service; Azure Active Directory and Azure AD are earlier names.
- [Microsoft Active Directory Domain Services](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/get-started/virtual-dc/active-directory-domain-services-overview) (COTS) — AD DS; Windows Server directory service, distinct from Entra ID.
- [Okta Workforce Identity](https://www.okta.com/products/workforce-identity/) (SaaS) — Workforce authentication, access, and identity management.
- [Ping Identity PingFederate](https://www.pingidentity.com/en/product/pingfederate.html) (COTS) — Federation server and single sign-on software.
- [Keycloak](https://www.keycloak.org/) (Open source) — Identity provider with authentication and federation services.
- [OneLogin](https://www.onelogin.com/product) (SaaS) — Workforce identity and single sign-on service.
- [IBM Verify](https://www.ibm.com/products/verify) (SaaS) — Identity and access management product portfolio.
- [FreeIPA](https://www.freeipa.org/) (Open source) — Linux identity, authentication, and policy management.
- [authentik](https://goauthentik.io/) (Open source) — Identity provider and application access software.

### Key management systems

- [AWS Key Management Service](https://aws.amazon.com/kms/) (SaaS) — AWS KMS; managed cryptographic key service.
- [Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/overview) (SaaS) — Manages keys, secrets, and certificates; identify the actual object type.
- [Google Cloud Key Management Service](https://cloud.google.com/security/products/security-key-management) (SaaS) — Cloud KMS; managed cryptographic key service.
- [Oracle Cloud Infrastructure Vault](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/Concepts/keyoverview.htm) (SaaS) — OCI Vault and Key Management; identify the key and vault service in use.
- [IBM Key Protect for IBM Cloud](https://www.ibm.com/products/key-protect) (SaaS) — Managed encryption key service for IBM Cloud.
- [Thales CipherTrust Manager](https://cpl.thalesgroup.com/encryption/ciphertrust-manager) (COTS) — Enterprise key management within the CipherTrust platform.
- [Entrust KeyControl](https://www.entrust.com/products/key-management/keycontrol) (COTS) — Enterprise encryption key management software.
- [Fortanix Data Security Manager](https://www.fortanix.com/platform/data-security-manager) (COTS) — DSM; key management and cryptographic services platform.
- [OpenStack Barbican](https://docs.openstack.org/barbican/latest/) (Open source) — OpenStack Key Manager service.
- [OpenBao Transit secrets engine](https://openbao.org/docs/secrets/transit/) (Open source) — OpenBao component providing cryptographic operations through managed keys.

### Secrets and privileged credential management

- [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/) (SaaS) — Managed storage and access for application secrets.
- [Google Cloud Secret Manager](https://cloud.google.com/security/products/secret-manager) (SaaS) — Managed secret storage and versioning.
- [HashiCorp Vault](https://developer.hashicorp.com/vault/docs) (COTS) — Secrets management software; identify the deployed edition and engines.
- [CyberArk Conjur](https://github.com/cyberark/conjur) (Open source) — The Conjur open-source project for machine and application secrets.
- [Delinea Secret Server](https://delinea.com/products/secret-server) (COTS) — Privileged account credential vault and management software.
- [BeyondTrust Password Safe](https://www.beyondtrust.com/products/password-safe) (COTS) — Privileged password, secrets, and session management.
- [Akeyless](https://www.akeyless.io/) (SaaS) — Identity and secrets management platform.
- [Doppler](https://www.doppler.com/) (SaaS) — Application secrets management and configuration delivery.
- [Infisical](https://infisical.com/) (SaaS) — Secrets management platform; identify hosted or self-hosted deployment.
- [1Password Secrets Automation](https://www.1password.dev/secrets-automation) (SaaS) — Developer and workload access to secrets stored in 1Password.

## 7. Protected data

### Data governance, discovery and classification

- [Microsoft Purview](https://learn.microsoft.com/en-us/purview/purview) (SaaS) — Data governance, security, and compliance portfolio; identify the component.
- [Collibra Data Governance](https://www.collibra.com/products/data-governance) (SaaS) — Business data definitions, ownership, policies, and governance workflows.
- [Alation Data Catalog](https://www.alation.com/product/data-catalog/) (COTS) — Data discovery and metadata catalog software.
- [BigID](https://bigid.com/) (COTS) — Data discovery, classification, and security platform.
- [IBM Guardium](https://www.ibm.com/products/guardium) (COTS) — Data security portfolio; identify the exact Guardium component.
- [OpenMetadata](https://open-metadata.org/) (Open source) — Metadata catalog, discovery, and data governance software.
- [Apache Atlas](https://github.com/apache/atlas) (Open source) — Metadata management and data governance framework.
- [DataHub](https://github.com/datahub-project/datahub) (Open source) — The DataHub open-source metadata and data discovery project.

### Databases and analytical data platforms

- [PostgreSQL](https://www.postgresql.org/about/) (Open source) — Postgres; relational database software.
- [MySQL Community Server](https://www.mysql.com/) (Open source) — Community edition of MySQL; editions and managed services differ.
- [MariaDB Server](https://mariadb.org/) (Open source) — MariaDB relational database server.
- [Oracle AI Database](https://www.oracle.com/database/) (COTS) — Oracle database portfolio; record the exact database release in use.
- [Microsoft SQL Server](https://www.microsoft.com/en-us/sql-server/) (COTS) — Relational database software; distinguish it from managed Azure services.
- [IBM Db2](https://www.ibm.com/products/db2) (COTS) — Db2 database portfolio; distinguish distributed and z/OS editions.
- [MongoDB Atlas](https://www.mongodb.com/products/platform/atlas-database) (SaaS) — Managed MongoDB database service.
- [Apache Cassandra](https://cassandra.apache.org/_/index.html) (Open source) — Distributed wide-column database software.
- [Redis Open Source](https://redis.io/open-source/) (Open source) — In-memory data store; identify the exact release and distribution.
- [Snowflake](https://docs.snowflake.com/en/user-guide/intro-key-concepts) (SaaS) — Managed cloud data and analytics platform.

### Storage, archives and backup

- [Amazon S3](https://aws.amazon.com/s3/) (SaaS) — Amazon Simple Storage Service; cloud object storage.
- [Azure Blob Storage](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-introduction) (SaaS) — Azure object storage for unstructured data.
- [Google Cloud Storage](https://cloud.google.com/storage) (SaaS) — Google Cloud object storage service.
- [NetApp ONTAP](https://www.netapp.com/ontap-data-management-software/) (COTS) — Storage operating and data management software.
- [Veeam Backup & Replication](https://www.veeam.com/products/veeam-data-platform/backup-recovery.html) (COTS) — Backup and recovery software within Veeam Data Platform.
- [Commvault Cloud](https://www.commvault.com/platform) (COTS) — Backup and cyber recovery portfolio; identify the deployment and component.
- [Rubrik Security Cloud](https://www.rubrik.com/products) (SaaS) — Data protection and cyber recovery platform.
- [Ceph](https://ceph.io/en/) (Open source) — Distributed object, block, and file storage software.
- [restic](https://restic.net/) (Open source) — Backup software with repository-based storage.

## 8. Distributed endpoints

### DNS, email and document communications

- [ISC BIND 9](https://www.isc.org/bind/) (Open source) — DNS name server software; DNSSEC configuration is a separate evidence question.
- [PowerDNS Authoritative Server](https://docs.powerdns.com/authoritative/index.html) (Open source) — Authoritative DNS server; distinguish it from PowerDNS Recursor.
- [Microsoft Exchange Online](https://learn.microsoft.com/en-us/exchange/exchange-online) (SaaS) — Hosted Exchange email service.
- [Microsoft Exchange Server](https://learn.microsoft.com/en-us/exchange/exchange-server) (COTS) — Exchange server software; identify the actual release and deployment.
- [Gmail for Google Workspace](https://workspace.google.com/products/gmail/) (SaaS) — Organizational email service within Google Workspace.
- [Proton Mail](https://proton.me/mail) (SaaS) — Hosted email service.
- [Dovecot](https://dovecot.org/) (Open source) — IMAP server software; identify the edition and configured mail services.
- [LibreOffice](https://www.libreoffice.org/) (Open source) — Office document software; locate document protection and signing workflows.
- [Adobe Acrobat](https://www.adobe.com/acrobat.html) (COTS) — PDF document software; distinguish desktop and online workflows.

### Embedded software and operational technology

- [Siemens STEP 7 in TIA Portal](https://www.siemens.com/en-us/products/tia-portal/step7/) (COTS) — PLC engineering software within TIA Portal.
- [Siemens SIMATIC S7-1500](https://www.siemens.com/en-gb/products/simatic/s7-1500/) (Hardware/platform) — PLC hardware platform; identify CPU, firmware, and engineering software separately.
- [Rockwell Automation Studio 5000 Logix Designer](https://www.rockwellautomation.com/en-us/products/software/factorytalk/designsuite/studio-5000.html) (COTS) — Industrial controller programming and engineering software.
- [Rockwell Automation FactoryTalk Optix](https://www.rockwellautomation.com/en-us/products/software/factorytalk/optix.html) (COTS) — Industrial HMI and visualization software platform.
- [CODESYS](https://www.codesys.com/) (COTS) — Industrial automation engineering and runtime software ecosystem.
- [Inductive Automation Ignition](https://inductiveautomation.com/ignition/) (COTS) — SCADA and industrial application software platform.
- [PTC Kepware Server](https://www.ptc.com/en/products/kepware/kepserverex) (COTS) — Industrial connectivity software; KEPServerEX is a recognition name in earlier records.
- [Zephyr](https://www.zephyrproject.org/) (Open source) — Embedded real-time operating system software.
- [FreeRTOS](https://www.freertos.org/) (Open source) — Embedded real-time operating system and libraries.
- [Eclipse Mosquitto](https://mosquitto.org/) (Open source) — MQTT message broker software used in device and other messaging systems.

### Endpoint management and device encryption

- [Microsoft Intune](https://learn.microsoft.com/en-us/intune/fundamentals/what-is-intune) (SaaS) — Endpoint, mobile device, and application management service.
- [Jamf Pro](https://www.jamf.com/products/jamf-pro/) (COTS) — Apple device management software.
- [Omnissa Workspace ONE UEM](https://www.omnissa.com/products/workspace-one-unified-endpoint-management/) (COTS) — Unified endpoint management software.
- [IBM MaaS360](https://www.ibm.com/products/maas360) (SaaS) — Unified endpoint and mobile device management service.
- [ManageEngine Endpoint Central](https://www.manageengine.com/products/desktop-central/) (COTS) — Endpoint management and security software.
- [Tanium Autonomous IT Platform](https://www.tanium.com/autonomous-it-platform) (COTS) — Endpoint visibility and management platform; identify the licensed modules.
- [Microsoft BitLocker](https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/) (COTS) — Windows volume encryption component.
- [Apple FileVault](https://support.apple.com/guide/mac-help/how-does-filevault-work-on-a-mac-flvlt001/mac) (COTS) — macOS volume encryption capability; distinguish configuration from device hardware.
- [cryptsetup](https://gitlab.com/cryptsetup/cryptsetup) (Open source) — Linux disk encryption tooling; LUKS is a related format name.
- [osquery](https://github.com/osquery/osquery) (Open source) — Operating system instrumentation and inventory software.

## 9. Specialized and regulated cryptography

### Mainframe platforms and security software

- [IBM z/OS](https://www.ibm.com/products/zos) (COTS) — Operating system software for IBM Z mainframes.
- [IBM Integrated Cryptographic Service Facility](https://www.ibm.com/docs/en/SSLTBW_3.2.0/pdf/csfb500_icsf_overview_hcr77f0.pdf) (COTS) — ICSF; z/OS cryptographic services software component.
- [IBM Resource Access Control Facility](https://www.ibm.com/products/resource-access-control-facility) (COTS) — RACF; z/OS security and access control component.
- [IBM zSecure](https://www.ibm.com/products/zsecure) (COTS) — Mainframe security administration and audit software portfolio.
- [IBM CICS Transaction Server for z/OS](https://www.ibm.com/products/cics-transaction-server) (COTS) — Mainframe transaction processing software.
- [IBM MQ for z/OS](https://www.ibm.com/products/mq/zos) (COTS) — Mainframe messaging middleware.
- [IBM Db2 for z/OS](https://www.ibm.com/products/db2-for-zos) (COTS) — Mainframe relational database edition.
- [Broadcom ACF2](https://www.broadcom.com/products/mainframe/security/acf2) (COTS) — ACF2 mainframe security software.
- [Broadcom Top Secret](https://www.broadcom.com/products/mainframe/security/top-secret) (COTS) — Top Secret z/OS mainframe security software.

### Payment, financial messaging and specialized transaction systems

- [Thales payShield 10K](https://cpl.thalesgroup.com/encryption/hardware-security-modules/payment-hsms/payshield-10k) (Hardware/platform) — Payment HSM appliance; identify firmware and host software separately.
- [Futurex Excrypt Plus](https://www.futurex.com/products/hardware-security-modules/excrypt-plus-payment-hsm) (Hardware/platform) — Payment and general-purpose HSM appliance.
- [AWS Payment Cryptography](https://aws.amazon.com/payment-cryptography/) (SaaS) — Managed payment cryptographic operations and key service.
- [Swift Alliance Access](https://www.swift.com/products/alliance-access) (COTS) — Financial messaging interface software.
- [IBM Sterling B2B Integrator](https://www.ibm.com/products/b2b-integrator) (COTS) — Business-to-business transaction and partner integration software.
- [Axway B2Bi](https://www.axway.com/en/products/b2b-integration) (COTS) — B2B and EDI transaction integration software.
- [OpenText Trading Grid](https://www.opentext.com/products/trading-grid) (SaaS) — Managed B2B integration and trading-partner transaction platform.
- [Hyperledger Fabric](https://www.lfdecentralizedtrust.org/projects/fabric) (Open source) — Permissioned distributed-ledger software; identify the specific network and components.

## 10. Governance and assurance

### Policy, risk and exception management

- [ServiceNow Policy and Compliance Management](https://www.servicenow.com/products/policy-compliance-management.html) (SaaS) — Policy, controls, compliance, and exception workflows.
- [Archer Policy Program Management](https://community.archerirm.com/hc/en-us/articles/52147321515155-Archer-Policy-Program-Management) (COTS) — Policy ownership, standards, and exception management.
- [IBM OpenPages](https://www.ibm.com/products/openpages) (COTS) — Governance, risk, and compliance software; identify the module.
- [LogicGate Risk Cloud](https://www.logicgate.ai/platform/) (SaaS) — Risk and compliance workflow platform.
- [Optro](https://optro.ai/auditboard-to-optro) (SaaS) — Audit, risk, and compliance platform; AuditBoard is the earlier brand name.
- [MetricStream Policy and Document Management](https://www.metricstream.com/products/policy-and-document-management.htm) (COTS) — Policy, attestation, and exception management software.
- [OneTrust Compliance Automation](https://www.onetrust.com/products/compliance-automation/) (SaaS) — Controls, policy, and compliance evidence management.
- [eramba Community](https://www.eramba.org/) (Open source) — Community edition of the eramba GRC software.
- [SimpleRisk Core](https://www.simplerisk.com/) (Open source) — Core governance, risk, and compliance software.
- [CISO Assistant Community](https://github.com/intuitem/ciso-assistant-community) (Open source) — Risk, controls, compliance, and audit management software.

### Vendor and third-party assurance

- [ServiceNow Third-party Risk Management](https://www.servicenow.com/products/third-party-risk-management.html) (SaaS) — Vendor risk assessment and review workflows.
- [OneTrust Third-Party Risk Management](https://www.onetrust.com/products/third-party-risk-management/) (SaaS) — Third-party assessment and risk management.
- [ProcessUnity](https://www.processunity.com/) (SaaS) — Third-party risk management and vendor assessment platform.
- [Vanta Third Party Risk Management](https://www.vanta.com/products/third-party-risk-management) (SaaS) — Vendor assessment and third-party risk workflows.
- [Drata Third-Party Risk Management](https://drata.com/products/third-party-risk-management) (SaaS) — Third-party inventory, assessments, and risk review.
- [Bitsight Vendor Risk Management](https://www.bitsight.com/products/vendor-risk-management) (SaaS) — Vendor assessments and risk management; ratings do not prove cryptographic behavior.
- [UpGuard Vendor Risk](https://www.upguard.com/product/vendor-risk) (SaaS) — Third-party assessment and vendor security monitoring.
- [Whistic](https://www.whistic.com/) (SaaS) — Vendor risk assessment and security evidence exchange platform.
