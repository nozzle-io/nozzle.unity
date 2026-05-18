namespace Nozzle
{
    public enum NozzleErrorCode
    {
        Ok = 0,
        Unknown = 1,
        InvalidArgument = 2,
        UnsupportedBackend = 3,
        UnsupportedFormat = 4,
        DeviceMismatch = 5,
        ResourceCreationFailed = 6,
        SharedHandleFailed = 7,
        SenderNotFound = 8,
        SenderClosed = 9,
        Timeout = 10,
        BackendError = 11,
        CommandFailed = 12,
    }

    public enum NozzleBackendType
    {
        Unknown = 0,
        D3D11 = 1,
        Metal = 2,
        OpenGL = 3,
        DmaBuf = 4,
    }

    public enum NozzleTextureFormat
    {
        Unknown = 0,
        R8_UNORM = 1,
        RG8_UNORM = 2,
        RGB8_UNORM = 3,
        RGBA8_UNORM = 4,
        BGRA8_UNORM = 5,
        RGBA8_SRGB = 6,
        BGRA8_SRGB = 7,
        R16_UNORM = 8,
        RG16_UNORM = 9,
        RGB16_UNORM = 10,
        RGBA16_UNORM = 11,
        R16_FLOAT = 12,
        RG16_FLOAT = 13,
        RGB16_FLOAT = 14,
        RGBA16_FLOAT = 15,
        R32_FLOAT = 16,
        RG32_FLOAT = 17,
        RGB32_FLOAT = 18,
        RGBA32_FLOAT = 19,
        R32_UINT = 20,
        RGBA32_UINT = 21,
        RGB32_UINT = 22,
        Depth32_FLOAT = 23,
    }

    public enum NozzleReceiveMode
    {
        LatestOnly = 0,
        SequentialBestEffort = 1,
    }

    public enum NozzleFrameStatus
    {
        New = 0,
        NoNew = 1,
        Dropped = 2,
        SenderClosed = 3,
        Error = 4,
    }

    public enum NozzleTransferMode
    {
        Unknown = 0,
        ZeroCopySharedTexture = 1,
        GpuCopy = 2,
        CpuCopy = 3,
    }

    public enum NozzleSyncMode
    {
        None = 0,
        AccessGuarded = 1,
        GpuFenceBestEffort = 2,
    }

    public enum NozzleTextureOrigin
    {
        TopLeft = 0,
        BottomLeft = 1,
    }

    public enum NozzleFormatSource
    {
        Unknown = 0,
        Requested = 1,
        CallerHint = 2,
        NativeObserved = 3,
    }

    public enum NozzleNativeFormatKind
    {
        Unknown = 0,
        MtlPixelFormat = 1,
        DxgiFormat = 2,
        DrmFourcc = 3,
        GlInternalFormat = 4,
    }

    public struct NozzleFrameInfo
    {
        public ulong FrameIndex;
        public ulong TimestampNs;
        public uint Width;
        public uint Height;
        public NozzleTextureFormat Format;
        public NozzleTextureFormat SemanticFormat;
        public NozzleTransferMode TransferMode;
        public NozzleSyncMode SyncMode;
        public uint DroppedFrameCount;
    }

    public struct NozzleSenderInfo
    {
        public string Name;
        public string ApplicationName;
        public string Id;
        public NozzleBackendType Backend;
    }
}
