# Storage Services Design Rubric

**Applies to:** Cloud Storage (GCS), Filestore

**Quick lookup (no rubric):** Check `fast-path.md` first (Cloud Storage → S3, deterministic)

## Deterministic Mapping

**Cloud Storage (`google_storage_bucket`) → S3 (`aws_s3_bucket`)**

Confidence: `deterministic` (always 1:1, no decision tree)

**Behavior preservation:**

- Bucket versioning → S3 versioning
- Lifecycle rules → S3 Lifecycle policies (a `SetStorageClass` action becomes a lifecycle transition; see [Storage class mapping](#storage-class-mapping))
- Storage class → the mapped S3 storage class (see [Storage class mapping](#storage-class-mapping))
- Access control (UNIFORM) → S3 Object Ownership "BucketOwnerEnforced" (ACLs disabled) + Bucket Policies
- Access control (FINE-GRAINED) → S3 Bucket Policies (ACLs disabled; translate per-object grants to policy conditions)
- Regional location → S3 region selection
- Encryption (default or CSEK) → S3 encryption (default AES-256 or KMS)

## GCS → S3 Attribute Mapping

| GCS Attribute                 | S3 Equivalent                                              | Notes                                                                              |
| ----------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `location` (region)           | `region`                                                   | Direct mapping; respect user's region choice                                       |
| `versioning_enabled`          | `versioning_enabled`                                       | 1:1 copy                                                                           |
| `lifecycle_rules`             | `lifecycle_rule`                                           | Adapt rule conditions; `SetStorageClass` → `transition` to the mapped class        |
| `storage_class`               | Per-object storage class (see Storage class mapping)       | S3 has no bucket default class; unset objects land in S3 Standard                  |
| `uniform_bucket_level_access` | `object_ownership = "BucketOwnerEnforced"` + bucket policy | ACLs disabled (AWS default since Apr 2023); use bucket policies for access control |
| `encryption` (CSEK)           | `sse_algorithm = "aws:kms"`                                | Use AWS KMS (customer-managed key)                                                 |
| `cors`                        | `cors_rule`                                                | 1:1 copy                                                                           |
| `retention_policy`            | `object_lock_configuration` (if applicable)                | Object Lock stricter than GCS retention                                            |

## Storage class mapping

S3 sets the storage class per object, not per bucket. An object written without one is stored in S3 Standard (`STANDARD`), so carry the GCS bucket's `storage_class` into the copy (for example the AWS DataSync S3 location's `S3StorageClass`) and into the application's upload calls.

| GCS `storage_class` | S3 storage class                              | S3 minimum storage duration | S3 access                                     |
| ------------------- | --------------------------------------------- | --------------------------- | --------------------------------------------- |
| `STANDARD`          | S3 Standard (`STANDARD`)                      | None                        | Milliseconds                                  |
| `NEARLINE`          | S3 Standard-IA (`STANDARD_IA`)                | 30 days (128 KB min. size)  | Milliseconds; per-GB retrieval fee            |
| `COLDLINE`          | S3 Glacier Instant Retrieval (`GLACIER_IR`)   | 90 days (128 KB min. size)  | Milliseconds; per-GB retrieval fee            |
| `ARCHIVE`           | S3 Glacier Instant Retrieval (`GLACIER_IR`)   | 90 days (128 KB min. size)  | Milliseconds; per-GB retrieval fee            |
| `ARCHIVE` (opt-in)  | S3 Glacier Deep Archive (`DEEP_ARCHIVE`)      | 180 days                    | Restore first; retrieval takes hours          |

- `ARCHIVE` maps to S3 Glacier Instant Retrieval by default because it serves reads in milliseconds with no restore step, so an application that reads archived objects directly keeps working. Use S3 Glacier Deep Archive only when the user confirms the data is read only after a planned restore; record that choice in the rationale.
- Compare each GCS class's own minimum storage duration with the S3 minimum above before moving data: deleting or transitioning an S3 object before its minimum is charged for the full minimum.
- A `storage_class` value not in this table is not guessed: record it as unmapped in the rationale.

**Lifecycle `SetStorageClass` action:** a GCS lifecycle rule whose action is `SetStorageClass` becomes an S3 lifecycle rule `transition` (`days`, `storage_class` = the mapped class above), with the rule's `age` condition carried over as `days`. S3 constraints to check:

- S3 lifecycle transitions only move objects down the storage-class waterfall (for example Standard → Standard-IA, never back). A GCS rule that moves objects to a warmer class has no S3 transition: record it as unmapped.
- An object must be stored at least 30 days before it can transition to S3 Standard-IA, so a `NEARLINE` rule with `age` below 30 needs `days = 30`.
- By default S3 lifecycle does not transition objects smaller than 128 KB; add an object-size filter if small objects must move.

## Output Schema

```json
{
  "gcp_type": "google_storage_bucket",
  "gcp_address": "my-app-assets",
  "gcp_config": {
    "location": "us-central1",
    "versioning_enabled": true,
    "lifecycle_rule": [
      {
        "action": "Delete",
        "condition": { "age_days": 90 }
      }
    ]
  },
  "aws_service": "S3",
  "aws_config": {
    "bucket": "my-app-assets-us-east-1",
    "versioning_enabled": true,
    "lifecycle_rule": [
      {
        "id": "delete-old-versions",
        "status": "Enabled",
        "noncurrent_version_expiration": { "days": 90 }
      }
    ],
    "region": "us-east-1"
  },
  "confidence": "deterministic",
  "rationale": "GCS → S3 is 1:1 deterministic; preserve versioning, lifecycle, encryption"
}
```

## Filestore → EFS

**Filestore (`google_filestore_instance`) → EFS (`aws_efs_file_system`)**

Confidence: `deterministic` (both are managed NFS file systems)

**Attribute mapping:**

| Filestore Attribute | EFS Equivalent                    | Notes                                      |
| ------------------- | --------------------------------- | ------------------------------------------ |
| `tier` (STANDARD)   | `throughput_mode = "bursting"`    | General purpose, burstable throughput      |
| `tier` (PREMIUM)    | `throughput_mode = "provisioned"` | High-performance, provisioned throughput   |
| `capacity_gb`       | No pre-provisioned size           | EFS scales automatically (no capacity set) |
| `network`           | `mount_target` subnet             | Place mount targets in same VPC subnets    |
| `file_shares.name`  | Mount target path                 | Preserve share name                        |

**Output Schema:**

```json
{
  "gcp_type": "google_filestore_instance",
  "gcp_address": "shared-data",
  "gcp_config": {
    "tier": "STANDARD",
    "capacity_gb": 1024,
    "network": "default"
  },
  "aws_service": "EFS",
  "aws_config": {
    "throughput_mode": "bursting",
    "performance_mode": "generalPurpose",
    "encrypted": true,
    "region": "us-east-1"
  },
  "confidence": "deterministic",
  "rationale": "Filestore → EFS is 1:1 deterministic; both are managed NFS"
}
```

## Notes

Cloud Storage maps 1:1 to S3. Storage classes and lifecycle `SetStorageClass` actions are translated per [Storage class mapping](#storage-class-mapping); a migrated bucket never defaults silently to S3 Standard.

For non-storage use cases (static site hosting, data lakes, etc.), the hosting compute service (Fargate, Amplify) determines architecture, not the bucket itself.
