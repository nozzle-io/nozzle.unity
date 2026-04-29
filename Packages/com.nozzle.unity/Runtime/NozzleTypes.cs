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
    }

    public enum NozzleBackendType
    {
        Unknown = 0,
        D3D11 = 1,
        Metal = 2,
        OpenGL = 3,
    }

    public enum NozzleTextureFormat
    {
        Unknown = 0,
        R8_UNORM = 1,
        RG8_UNORM = 2,
        RGBA8_UNORM = 3,
        BGRA8_UNORM = 4,
        RGBA8_SRGB = 5,
        BGRA8_SRGB = 6,
        R16_UNORM = 7,
        RG16_UNORM = 8,
        RGBA16_UNORM = 9,
        R16_FLOAT = 10,
        RG16_FLOAT = 11,
        RGBA16_FLOAT = 12,
        R32_FLOAT = 13,
        RG32_FLOAT = 14,
        RGBA32_FLOAT = 15,
        R32_UINT = 16,
        RGBA32_UINT = 17,
        Depth32_FLOAT = 18,
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

    public struct NozzleFrameInfo
    {
        public ulong FrameIndex;
        public ulong TimestampNs;
        public uint Width;
        public uint Height;
        public NozzleTextureFormat Format;
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
