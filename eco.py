"""
// Copyright (c) William Newport
// SPDX-License-Identifier: BUSL-1.1

This is a starter datasurface repository. It defines a simple Ecosystem using YellowDataPlatform with Live and Forensic modes.
It will generate 2 pipelines, one with live records only and the other with full milestoning.
"""

from datasurface.md import Team, GovernanceZoneDeclaration, GovernanceZone, InfrastructureVendor, InfrastructureLocation, \
    TeamDeclaration, DataTransformer
from datasurface.md import Ecosystem, LocationKey, DataPlatformManagedDataContainer
from datasurface.md.credential import Credential, CredentialType
from datasurface.md.documentation import PlainTextDocumentation
from datasurface.md.repo import GitHubRepository
from datasurface.platforms.yellow import YellowDataPlatform, YellowMilestoneStrategy
from datasurface.md import CloudVendor, DefaultDataPlatform, \
        DataPlatformKey, WorkspacePlatformConfig
from datasurface.md import ValidationTree
from datasurface.md.governance import Datastore, Dataset, SQLSnapshotIngestion, HostPortPair, CronTrigger, IngestionConsistencyType, \
    ConsumerRetentionRequirements, DataMilestoningStrategy, DataLatency
from datasurface.md.schema import DDLTable, DDLColumn, NullableStatus, PrimaryKeyStatus
from datasurface.md.types import VarChar, Date
from datasurface.md.policy import SimpleDC, SimpleDCTypes
from datasurface.md import Workspace, DatasetSink, DatasetGroup, PostgresDatabase
from datasurface.md.codeartifact import PythonRepoCodeArtifact

KUB_NAME_SPACE: str = "ns-yellow-starter"  # This is the namespace you want to use for your kubernetes environment
GH_REPO_OWNER: str = "billynewport"  # Change to your github username
GH_REPO_NAME: str = "yellow_starter"  # Change to your github repository name containing this project
GH_DT_REPO_NAME: str = "yellow_starter"  # For now, we use the same repo for the transformer


def createEcosystem() -> Ecosystem:
    """This is a very simple test model with a single datastore and dataset.
    It is used to test the YellowDataPlatform."""

    # Kubernetes merge database configuration
    k8s_merge_datacontainer: PostgresDatabase = PostgresDatabase(
        "K8sMergeDB",  # Container name for Kubernetes deployment
        hostPort=HostPortPair(f"pg-data.{KUB_NAME_SPACE}.svc.cluster.local", 5432),
        locations={LocationKey("MyCorp:USA/NY_1")},  # Kubernetes cluster location
        databaseName="datasurface_merge"  # The database we created
    )

    git: Credential = Credential("git", CredentialType.API_TOKEN)

    ecosys: Ecosystem = Ecosystem(
        name="YellowStarter",
        repo=GitHubRepository(f"{GH_REPO_OWNER}/{GH_REPO_NAME}", "main", credential=git),
        data_platforms=[
            YellowDataPlatform(
                name="YellowLive",
                locs={LocationKey("MyCorp:USA/NY_1")},
                doc=PlainTextDocumentation("Live Yellow DataPlatform"),
                namespace=KUB_NAME_SPACE,
                connectCredentials=Credential("connect", CredentialType.API_TOKEN),
                postgresCredential=Credential("postgres", CredentialType.USER_PASSWORD),
                gitCredential=git,
                slackCredential=Credential("slack", CredentialType.API_TOKEN),
                merge_datacontainer=k8s_merge_datacontainer,  # ✅ Kubernetes merge DB
                airflowName="airflow",
                milestoneStrategy=YellowMilestoneStrategy.LIVE_ONLY
                ),
            YellowDataPlatform(
                "YellowForensic",
                locs={LocationKey("MyCorp:USA/NY_1")},
                doc=PlainTextDocumentation("Forensic Yellow DataPlatform"),
                namespace=KUB_NAME_SPACE,
                connectCredentials=Credential("connect", CredentialType.API_TOKEN),
                postgresCredential=Credential("postgres", CredentialType.USER_PASSWORD),
                gitCredential=Credential("git", CredentialType.API_TOKEN),
                slackCredential=Credential("slack", CredentialType.API_TOKEN),
                merge_datacontainer=k8s_merge_datacontainer,  # ✅ Kubernetes merge DB
                airflowName="airflow",
                milestoneStrategy=YellowMilestoneStrategy.BATCH_MILESTONED
                )
        ],
        default_data_platform=DefaultDataPlatform(DataPlatformKey("YellowLive")),
        governance_zone_declarations=[
            GovernanceZoneDeclaration("USA", GitHubRepository(f"{GH_REPO_OWNER}/{GH_REPO_NAME}", "gzmain"))
        ],
        infrastructure_vendors=[
            # Onsite data centers
            InfrastructureVendor(
                name="MyCorp",
                cloud_vendor=CloudVendor.PRIVATE,
                documentation=PlainTextDocumentation("Private company data centers"),
                locations=[
                    InfrastructureLocation(
                        name="USA",
                        locations=[
                            InfrastructureLocation(name="NY_1")
                        ]
                    )
                ]
            )
        ]
    )
    gz: GovernanceZone = ecosys.getZoneOrThrow("USA")

    # Add a team to the governance zone
    gz.add(TeamDeclaration(
        "team1",
        GitHubRepository(f"{GH_REPO_OWNER}/{GH_REPO_NAME}", "team1", credential=git)
        ))

    team: Team = gz.getTeamOrThrow("team1")
    team.add(
        Datastore(
            "Store1",
            documentation=PlainTextDocumentation("Test datastore"),
            capture_metadata=SQLSnapshotIngestion(
                PostgresDatabase(
                    "CustomerDB",  # Model name for database
                    hostPort=HostPortPair(f"pg-data.{KUB_NAME_SPACE}.svc.cluster.local", 5432),
                    locations={LocationKey("MyCorp:USA/NY_1")},  # Locations for database
                    databaseName="customer_db"  # Database name
                ),
                CronTrigger("Every 5 minute", "*/5 * * * *"),  # Cron trigger for ingestion
                IngestionConsistencyType.MULTI_DATASET,  # Ingestion consistency type
                Credential("postgres", CredentialType.USER_PASSWORD),  # Credential for platform to read from database
                ),
            datasets=[
                Dataset(
                    "customers",
                    schema=DDLTable(
                        columns=[
                            DDLColumn("id", VarChar(20), nullable=NullableStatus.NOT_NULLABLE, primary_key=PrimaryKeyStatus.PK),
                            DDLColumn("firstname", VarChar(100), nullable=NullableStatus.NOT_NULLABLE),
                            DDLColumn("lastname", VarChar(100), nullable=NullableStatus.NOT_NULLABLE),
                            DDLColumn("dob", Date(), nullable=NullableStatus.NOT_NULLABLE),
                            DDLColumn("email", VarChar(100)),
                            DDLColumn("phone", VarChar(100)),
                            DDLColumn("primaryaddressid", VarChar(20)),
                            DDLColumn("billingaddressid", VarChar(20))
                        ]
                    ),
                    classifications=[SimpleDC(SimpleDCTypes.CPI, "Customer")]
                ),
                Dataset(
                    "addresses",
                    schema=DDLTable(
                        columns=[
                            DDLColumn("id", VarChar(20), nullable=NullableStatus.NOT_NULLABLE, primary_key=PrimaryKeyStatus.PK),
                            DDLColumn("customerid", VarChar(20), nullable=NullableStatus.NOT_NULLABLE),
                            DDLColumn("streetname", VarChar(100), nullable=NullableStatus.NOT_NULLABLE),
                            DDLColumn("city", VarChar(100), nullable=NullableStatus.NOT_NULLABLE),
                            DDLColumn("state", VarChar(100), nullable=NullableStatus.NOT_NULLABLE),
                            DDLColumn("zipcode", VarChar(30), nullable=NullableStatus.NOT_NULLABLE)
                        ]
                    ),
                    classifications=[SimpleDC(SimpleDCTypes.CPI, "Address")]
                )
            ]
        ),
        Workspace(
            "Consumer1",
            DataPlatformManagedDataContainer("Consumer1 container"),
            DatasetGroup(
                "LiveDSG",
                sinks=[
                    DatasetSink("Store1", "customers"),
                    DatasetSink("Store1", "addresses"),
                    DatasetSink("MaskedCustomers", "customers")
                ],
                platform_chooser=WorkspacePlatformConfig(
                    hist=ConsumerRetentionRequirements(
                        r=DataMilestoningStrategy.LIVE_ONLY,
                        latency=DataLatency.MINUTES,
                        regulator=None
                    )
                ),
            ),
            DatasetGroup(
                "ForensicDSG",
                sinks=[
                    DatasetSink("Store1", "customers"),
                    DatasetSink("Store1", "addresses"),
                    DatasetSink("MaskedCustomers", "customers")
                ],
                platform_chooser=WorkspacePlatformConfig(
                    hist=ConsumerRetentionRequirements(
                        r=DataMilestoningStrategy.FORENSIC,
                        latency=DataLatency.MINUTES,
                        regulator=None
                    )
                )
            )
        ),
        Workspace(
            "MaskedStoreGenerator",
            DataPlatformManagedDataContainer("MaskedStoreGenerator container"),
            DatasetGroup(
                "Original",
                sinks=[DatasetSink("Store1", "customers")]
            ),
            DataTransformer(
                name="MaskedCustomerGenerator",
                code=PythonRepoCodeArtifact(GitHubRepository(f"{GH_REPO_OWNER}/{GH_DT_REPO_NAME}", "main", credential=git), "main"),
                trigger=CronTrigger("Every 10 minute", "*/10 * * * *"),
                store=Datastore(
                    name="MaskedCustomers",
                    documentation=PlainTextDocumentation("MaskedCustomers datastore"),
                    datasets=[
                        Dataset(
                            "customers",
                            schema=DDLTable(
                                columns=[
                                    DDLColumn("id", VarChar(20), nullable=NullableStatus.NOT_NULLABLE, primary_key=PrimaryKeyStatus.PK),
                                    DDLColumn("firstname", VarChar(100), nullable=NullableStatus.NOT_NULLABLE),
                                    DDLColumn("lastname", VarChar(100), nullable=NullableStatus.NOT_NULLABLE),
                                    DDLColumn("dob", Date(), nullable=NullableStatus.NOT_NULLABLE),
                                    DDLColumn("email", VarChar(100)),
                                    DDLColumn("phone", VarChar(100)),
                                    DDLColumn("primaryaddressid", VarChar(20)),
                                    DDLColumn("billingaddressid", VarChar(20))
                                ]
                            ),
                            classifications=[SimpleDC(SimpleDCTypes.PUB, "Customer")]
                        )
                    ]
                )
            )
        )
    )

    tree: ValidationTree = ecosys.lintAndHydrateCaches()
    if (tree.hasErrors()):
        tree.printTree()
        raise Exception("Ecosystem validation failed")
    return ecosys


def test_Validate():
    ecosys: Ecosystem = createEcosystem()
    vTree: ValidationTree = ecosys.lintAndHydrateCaches()
    if (vTree.hasErrors()):
        print("Ecosystem validation failed with errors:")
        vTree.printTree()
        raise Exception("Ecosystem validation failed")
    else:
        print("Ecosystem validated OK")
        if vTree.hasWarnings():
            print("Note: There are some warnings:")
            vTree.printTree()


if __name__ == "__main__":
    test_Validate()
