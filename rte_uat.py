"""
// Copyright (c) William Newport
// SPDX-License-Identifier: BUSL-1.1

This is a starter datasurface repository. It defines a simple Ecosystem using YellowDataPlatform with Live and Forensic modes. It
ingests data from a single source, using a Workspace to produce a masked version of that data and provides consumer Workspaces
to that data in Postgres, SQLServer, Oracle and DB2 using CQRS.

It will generate 2 pipelines, one with live records only (SCD1) and the other with full milestoning (SCD2).
"""

from datasurface.md import DataTransformerExecutionPlacement, LocationKey
from datasurface.md.containers import HostPortPair
from datasurface.md.credential import Credential, CredentialType
from datasurface.md.documentation import PlainTextDocumentation
from datasurface.md import StorageRequirement, ProductionStatus
from datasurface.platforms.yellow import YellowDataPlatform, YellowMilestoneStrategy, YellowPlatformServiceProvider, K8sResourceLimits
from datasurface.md import PostgresDatabase, ConsumerReplicaGroup, CronTrigger, RuntimeEnvironment, Ecosystem, PSPDeclaration
from datasurface.platforms.yellow.assembly import GitCacheConfig, YellowExternalSingleDatabaseAssembly
from datasurface.md.containers import SQLServerDatabase
from datasurface.platforms.yellow.yellow_dp import K8sDataTransformerHint
from datasurface.md.repo import VersionPatternReleaseSelector, GitHubRepository, ReleaseType, VersionPatterns
UAT_KUB_NAME_SPACE: str = "ns-yellow-starter-uat"  # This is the namespace you want to use for your kubernetes environment


def createPSP() -> YellowPlatformServiceProvider:
    # Kubernetes merge database configuration
    k8s_merge_datacontainer: PostgresDatabase = PostgresDatabase(
        "K8sMergeDB",  # Container name for Kubernetes deployment
        hostPort=HostPortPair("postgres-uat", 5432),
        locations={LocationKey("MyCorp:USA/NY_1")},  # Kubernetes cluster location
        productionStatus=ProductionStatus.NOT_PRODUCTION,
        databaseName="datasurface_merge_uat"  # The database we created
    )

    git_config: GitCacheConfig = GitCacheConfig(
        enabled=True,
        access_mode="ReadWriteOnce",
        storageClass="longhorn"
    )
    yp_assembly: YellowExternalSingleDatabaseAssembly = YellowExternalSingleDatabaseAssembly(
        name="Test_DP_UAT",
        namespace=f"{UAT_KUB_NAME_SPACE}",
        git_cache_config=git_config,
        afHostPortPair=HostPortPair("postgres-uat", 5432),
        afWebserverResourceLimits=K8sResourceLimits(
            requested_memory=StorageRequirement("1G"),
            limits_memory=StorageRequirement("2G"),
            requested_cpu=1.0,
            limits_cpu=2.0
        ),
        afSchedulerResourceLimits=K8sResourceLimits(
            requested_memory=StorageRequirement("3G"),
            limits_memory=StorageRequirement("5G"),
            requested_cpu=2.0,
            limits_cpu=4.0
        )
    )

    psp: YellowPlatformServiceProvider = YellowPlatformServiceProvider(
        "Test_DP_UAT",
        {LocationKey("MyCorp:USA/NY_1")},
        PlainTextDocumentation("Test"),
        gitCredential=Credential("git", CredentialType.API_TOKEN),
        connectCredentials=Credential("connect", CredentialType.API_TOKEN),
        mergeRW_Credential=Credential("postgres", CredentialType.USER_PASSWORD),
        yp_assembly=yp_assembly,
        merge_datacontainer=k8s_merge_datacontainer,
        pv_storage_class="longhorn",
        dataPlatforms=[
            YellowDataPlatform(
                name="YellowLiveUAT",
                doc=PlainTextDocumentation("Live Yellow DataPlatform"),
                milestoneStrategy=YellowMilestoneStrategy.SCD1
                ),
            YellowDataPlatform(
                "YellowForensicUAT",
                doc=PlainTextDocumentation("Forensic Yellow DataPlatform"),
                milestoneStrategy=YellowMilestoneStrategy.SCD2
                )
        ],
        consumerReplicaGroups=[
            ConsumerReplicaGroup(
                name="postgres-uat",
                dataContainers={
                    PostgresDatabase(
                        "Postgres",
                        hostPort=HostPortPair("postgres-uat", 5432),
                        locations={LocationKey("MyCorp:USA/NY_1")},
                        productionStatus=ProductionStatus.NOT_PRODUCTION,
                        databaseName="postgres-cqrs-uat"
                    )
                },
                workspaceNames={"Consumer1"},
                trigger=CronTrigger("Every 5 minute", "*/5 * * * *"),
                credential=Credential("postgres", CredentialType.USER_PASSWORD)
            ),
            ConsumerReplicaGroup(
                name="SQLServer-uat",
                dataContainers={
                    SQLServerDatabase(
                        "SQLServer-uat",
                        hostPort=HostPortPair("sqlserver-uat", 1433),
                        locations={LocationKey("MyCorp:USA/NY_1")},
                        productionStatus=ProductionStatus.NOT_PRODUCTION,
                        databaseName="cqrs"
                    )
                },
                workspaceNames={"Consumer1", "MaskedStoreGenerator"},
                trigger=CronTrigger("Every 5 minute", "*/5 * * * *"),
                credential=Credential("sa", CredentialType.USER_PASSWORD)
            )
        ],
        hints=[
            # Run the MaskedCustomer data transformer on the SQLServer consumer replica group
            K8sDataTransformerHint(
                workspaceName="MaskedStoreGenerator",
                kv={},
                resourceLimits=K8sResourceLimits(
                    requested_memory=StorageRequirement("1G"),
                    limits_memory=StorageRequirement("2G"),
                    requested_cpu=1.0,
                    limits_cpu=2.0
                ),
                executionPlacement=DataTransformerExecutionPlacement(
                    crgName="SQLServer-uat",
                    dcName="SQLServer-uat"
                )
            )
        ]
    )
    return psp


def createUATRTE(ecosys: Ecosystem) -> RuntimeEnvironment:
    assert isinstance(ecosys.owningRepo, GitHubRepository)

    psp: YellowPlatformServiceProvider = createPSP()
    rte: RuntimeEnvironment = ecosys.getRuntimeEnvironmentOrThrow("uat")
    # Allow edits using RTE repository
    rte.configure(VersionPatternReleaseSelector(
        VersionPatterns.VN_N_N+"-uat", ReleaseType.ALL),
        [PSPDeclaration(psp.name, rte.owningRepo)],
        ProductionStatus.NOT_PRODUCTION)
    rte.setPSP(psp)
    return rte
