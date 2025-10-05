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
from datasurface.md import StorageRequirement
from datasurface.platforms.yellow import YellowDataPlatform, YellowMilestoneStrategy, YellowPlatformServiceProvider, K8sResourceLimits
from datasurface.md import PostgresDatabase, ConsumerReplicaGroup, CronTrigger
from datasurface.platforms.yellow.assembly import GitCacheConfig, YellowExternalSingleDatabaseAssembly
from datasurface.md.containers import SQLServerDatabase
from datasurface.platforms.yellow.yellow_dp import K8sDataTransformerHint
KUB_NAME_SPACE: str = "ns-yellow-starter"  # This is the namespace you want to use for your kubernetes environment


def createPSP() -> YellowPlatformServiceProvider:
    # Kubernetes merge database configuration
    k8s_merge_datacontainer: PostgresDatabase = PostgresDatabase(
        "K8sMergeDB",  # Container name for Kubernetes deployment
        hostPort=HostPortPair("postgres-docker", 5432),
        locations={LocationKey("MyCorp:USA/NY_1")},  # Kubernetes cluster location
        databaseName="datasurface_merge"  # The database we created
    )

    git_config: GitCacheConfig = GitCacheConfig(
        enabled=True,
        access_mode="ReadWriteOnce",
        storageClass="standard"
    )
    yp_assembly: YellowExternalSingleDatabaseAssembly = YellowExternalSingleDatabaseAssembly(
        name="Test_DP",
        namespace=f"{KUB_NAME_SPACE}",
        git_cache_config=git_config,
        afHostPortPair=HostPortPair(f"af-data.{KUB_NAME_SPACE}.svc.cluster.local", 5432),
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
        "Test_DP",
        {LocationKey("MyCorp:USA/NY_1")},
        PlainTextDocumentation("Test"),
        gitCredential=Credential("git", CredentialType.API_TOKEN),
        connectCredentials=Credential("connect", CredentialType.API_TOKEN),
        mergeRW_Credential=Credential("postgres", CredentialType.USER_PASSWORD),
        yp_assembly=yp_assembly,
        merge_datacontainer=k8s_merge_datacontainer,
        pv_storage_class="standard",
        dataPlatforms=[
            YellowDataPlatform(
                name="YellowLive",
                doc=PlainTextDocumentation("Live Yellow DataPlatform"),
                milestoneStrategy=YellowMilestoneStrategy.SCD1
                ),
            YellowDataPlatform(
                "YellowForensic",
                doc=PlainTextDocumentation("Forensic Yellow DataPlatform"),
                milestoneStrategy=YellowMilestoneStrategy.SCD2
                )
        ],
        consumerReplicaGroups=[
            ConsumerReplicaGroup(
                name="postgres",
                dataContainers={
                    PostgresDatabase(
                        "Postgres",
                        hostPort=HostPortPair("host.docker.internal", 5432),
                        locations={LocationKey("MyCorp:USA/NY_1")},
                        databaseName="postgres-cqrs"
                    )
                },
                workspaceNames={"Consumer1"},
                trigger=CronTrigger("Every 5 minute", "*/5 * * * *"),
                credential=Credential("postgres", CredentialType.USER_PASSWORD)
            ),
            ConsumerReplicaGroup(
                name="SQLServer",
                dataContainers={
                    SQLServerDatabase(
                        "SQLServer",
                        hostPort=HostPortPair("host.docker.internal", 1433),
                        locations={LocationKey("MyCorp:USA/NY_1")},
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
                    crgName="SQLServer",
                    dcName="SQLServer"
                )
            )
        ]
    )
    return psp
