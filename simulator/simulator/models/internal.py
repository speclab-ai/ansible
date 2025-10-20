from typing import List, Dict, Optional
from pydantic import BaseModel

# Moved to infra layer - re-export for backwards compatibility
from simulator.infra.request_context import RequestContext
from simulator.infra.network import Message, NetworkMessage


class OSTInfo(BaseModel):
    """Information about an Object Storage Target."""
    ost_id: str
    ost_index: int  # Unique index for striping
    oss_id: str  # Parent Object Storage Server
    capacity_bytes: int = 1_000_000_000  # 1GB default
    used_bytes: int = 0
    is_available: bool = True
    availability_zone: str


class MDTInfo(BaseModel):
    """Information about a Metadata Target."""
    mdt_id: str
    mdt_index: int  # For DNE (Distributed Namespace)
    mds_id: str  # Parent Metadata Server
    is_available: bool = True
    availability_zone: str


class ServerInfo(BaseModel):
    """Information about a Lustre server (MDS or OSS)."""
    server_id: str
    server_type: str  # "MDS" or "OSS"
    address: str
    availability_zone: str
    is_up: bool = True


class FileMetadata(BaseModel):
    """File metadata stored on MDS."""
    fid: str  # File Identifier
    path: str
    is_directory: bool = False
    is_symlink: bool = False
    symlink_target: Optional[str] = None  # Target path for symlinks
    stripe_count: int = 1
    stripe_size: int = 1048576  # 1MB default
    ost_indices: List[int] = []  # OST indices for striping
    size_bytes: int = 0

    # Extended attributes
    mode: int = 0o644  # File permissions (default: rw-r--r--)
    uid: int = 0  # User ID
    gid: int = 0  # Group ID
    nlink: int = 1  # Number of hard links

    # Timestamps
    atime: float = 0.0  # Access time
    mtime: float = 0.0  # Modification time
    ctime: float = 0.0  # Change time (metadata)

    parent_fid: Optional[str] = None  # Parent directory FID


class FileStripe(BaseModel):
    """Information about a file stripe stored on an OST."""
    fid: str  # File Identifier
    stripe_index: int  # Which stripe this is (0, 1, 2, ...)
    ost_index: int  # Which OST stores this stripe
    data: Dict[int, str] = {}  # offset -> data mapping
    size_bytes: int = 0


class LockInfo(BaseModel):
    """Distributed lock information (LDLM)."""
    lock_id: str
    fid: str  # File Identifier
    lock_type: str  # "READ" or "WRITE"
    extent_start: int = 0
    extent_end: int = -1  # -1 for EOF
    client_id: str
    granted_time: float = 0.0


class ServerStatusMessage(BaseModel):
    """Message for server registration/status updates."""
    server_info: ServerInfo
    status: str  # 'REGISTER', 'UNREGISTER', 'HEARTBEAT'


class OSTStatusMessage(BaseModel):
    """Message for OST status updates."""
    ost_info: OSTInfo
    status: str  # 'ACTIVE', 'DEGRADED', 'OFFLINE'


class MDTStatusMessage(BaseModel):
    """Message for MDT status updates."""
    mdt_info: MDTInfo
    status: str  # 'ACTIVE', 'DEGRADED', 'OFFLINE'


class ConfigUpdateMessage(BaseModel):
    """Configuration update from MGS to other servers."""
    config_version: int
    ost_list: List[OSTInfo] = []
    mdt_list: List[MDTInfo] = []
    server_list: List[ServerInfo] = []


class StripeAllocationRequest(BaseModel):
    """Internal request from MDS to allocate stripes for a file."""
    fid: str
    stripe_count: int
    stripe_size: int


class StripeAllocationResponse(BaseModel):
    """Response with allocated OST indices."""
    fid: str
    ost_indices: List[int]
    success: bool = True
