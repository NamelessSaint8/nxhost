// Texture views may be registered for storage after the underlying image was
// created. NVN's IMAGE hint is not a complete declaration of later uses.
// compatible_features covers an sRGB image's linear view under EXTENDED_USAGE.
#ifndef DM_VK_IMAGE_USAGE_H
#define DM_VK_IMAGE_USAGE_H
static inline VkImageUsageFlags vk_texture_image_usage(VkFormatFeatureFlags features,
                                                       VkFormatFeatureFlags compatible_features,
                                                       int storage_colour) {
    VkImageUsageFlags usage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    if (features & VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT) usage |= VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
    if (features & VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT) usage |= VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT;
    if (storage_colour && ((features | compatible_features) & VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT)) usage |= VK_IMAGE_USAGE_STORAGE_BIT;
    return usage;
}
#endif
