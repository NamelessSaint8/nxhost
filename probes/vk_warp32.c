// Synthetic translated Ampere operations against CPU references, including
// safe legacy negative controls on wave64. No game files, window or heap.
// NDK clang -O2 -Wall -Wextra vk_warp32.c -o vk_warp32 -lvulkan
// vk_warp32 <make_warp32_proof.py output>
#include <vulkan/vulkan.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define VK(call) do { VkResult r=(call); if(r){fprintf(stderr,"%s: %d\n",#call,r);exit(2);} } while(0)
static void *read_file(const char *root,const char *name,const char *suffix,size_t *size){
    char path[2048];snprintf(path,sizeof path,"%s/%s%s",root,name,suffix);FILE *f=fopen(path,"rb");
    if(!f){perror(path);exit(2);}fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
    if(n<=0){fprintf(stderr,"empty input %s\n",path);exit(2);}void *p=malloc((size_t)n);
    if(!p||fread(p,1,(size_t)n,f)!=(size_t)n)exit(2);fclose(f);*size=(size_t)n;return p;
}
int main(int argc,char **argv){
    if(argc!=2){fprintf(stderr,"usage: vk_warp32 shader-folder\n");return 2;}
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.apiVersion=VK_API_VERSION_1_2};
    VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app};VkInstance instance;VK(vkCreateInstance(&ici,NULL,&instance));
    uint32_t count=1;VkPhysicalDevice pd;VK(vkEnumeratePhysicalDevices(instance,&count,&pd));if(!count)return 2;
    VkPhysicalDeviceSubgroupProperties sg={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SUBGROUP_PROPERTIES};
    VkPhysicalDeviceProperties2 props={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,.pNext=&sg};vkGetPhysicalDeviceProperties2(pd,&props);
    printf("%s: physical subgroup %u\n",props.properties.deviceName,sg.subgroupSize);
    uint32_t nq=0;vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,NULL);VkQueueFamilyProperties *families=calloc(nq,sizeof *families);vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,families);
    uint32_t family=0;while(family<nq&&!(families[family].queueFlags&VK_QUEUE_COMPUTE_BIT))family++;free(families);if(family==nq)return 2;
    float priority=1;VkDeviceQueueCreateInfo qi={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=family,.queueCount=1,.pQueuePriorities=&priority};
    VkPhysicalDeviceFeatures features;vkGetPhysicalDeviceFeatures(pd,&features);
    VkDeviceCreateInfo di={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&qi,.pEnabledFeatures=&features};VkDevice device;VK(vkCreateDevice(pd,&di,NULL,&device));VkQueue queue;vkGetDeviceQueue(device,family,0,&queue);
    VkBufferCreateInfo bi={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=1024,.usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};VkBuffer buffer;VK(vkCreateBuffer(device,&bi,NULL,&buffer));VkMemoryRequirements need;vkGetBufferMemoryRequirements(device,buffer,&need);
    VkPhysicalDeviceMemoryProperties memory;vkGetPhysicalDeviceMemoryProperties(pd,&memory);uint32_t mt=0;
    while(mt<memory.memoryTypeCount&&(!(need.memoryTypeBits&(1u<<mt))||(memory.memoryTypes[mt].propertyFlags&(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))!=(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)))mt++;
    if(mt==memory.memoryTypeCount)return 2;VkMemoryAllocateInfo mi={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=need.size,.memoryTypeIndex=mt};VkDeviceMemory mem;VK(vkAllocateMemory(device,&mi,NULL,&mem));VK(vkBindBufferMemory(device,buffer,mem,0));uint32_t *mapped;VK(vkMapMemory(device,mem,0,1024,0,(void**)&mapped));
    VkDescriptorSetLayoutBinding binding={.binding=31,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT};VkDescriptorSetLayoutCreateInfo li={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=1,.pBindings=&binding};VkDescriptorSetLayout dsl;VK(vkCreateDescriptorSetLayout(device,&li,NULL,&dsl));
    VkPipelineLayoutCreateInfo pli={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=1,.pSetLayouts=&dsl};VkPipelineLayout layout;VK(vkCreatePipelineLayout(device,&pli,NULL,&layout));
    VkDescriptorPoolSize ps={VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1};VkDescriptorPoolCreateInfo dpi={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,.maxSets=1,.poolSizeCount=1,.pPoolSizes=&ps};VkDescriptorPool pool;VK(vkCreateDescriptorPool(device,&dpi,NULL,&pool));VkDescriptorSetAllocateInfo sai={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=pool,.descriptorSetCount=1,.pSetLayouts=&dsl};VkDescriptorSet set;VK(vkAllocateDescriptorSets(device,&sai,&set));
    VkDescriptorBufferInfo db={buffer,0,1024};VkWriteDescriptorSet write={.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=set,.dstBinding=31,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.pBufferInfo=&db};vkUpdateDescriptorSets(device,1,&write,0,NULL);
    VkCommandPoolCreateInfo cpi={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,.queueFamilyIndex=family};VkCommandPool cp;VK(vkCreateCommandPool(device,&cpi,NULL,&cp));VkCommandBufferAllocateInfo cai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=cp,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};VkCommandBuffer cmd;VK(vkAllocateCommandBuffers(device,&cai,&cmd));
    char path[2048],name[128];snprintf(path,sizeof path,"%s/manifest.tsv",argv[1]);FILE *manifest=fopen(path,"r");if(!manifest){perror(path);return 2;}unsigned words,legacy,checks=0,failed=0;
    while(fscanf(manifest,"%127s %u %u",name,&words,&legacy)==3){
        if(!words||words>256||legacy>3)return 2;if(legacy==1&&sg.subgroupSize==32){printf("SKIP %s negative control on wave32\n",name);continue;}
        size_t size;
        uint32_t *expected=read_file(argv[1],name,".expected",&size);if(size!=words*4u)return 2;
        int precision_ok=1;
        for(unsigned variant=0;variant<(legacy>=2?2u:1u);variant++){
        void *binary=read_file(argv[1],name,legacy>=2&&variant==0?".reference.vk.spv":".vk.spv",&size);VkShaderModuleCreateInfo sci={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=size,.pCode=binary};VkShaderModule module;VK(vkCreateShaderModule(device,&sci,NULL,&module));free(binary);
        VkComputePipelineCreateInfo pci={.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,.stage={.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_COMPUTE_BIT,.module=module,.pName="main"},.layout=layout};VkPipeline pipeline;VK(vkCreateComputePipelines(device,VK_NULL_HANDLE,1,&pci,NULL,&pipeline));
        memset(mapped,0xcd,1024);VK(vkResetCommandBuffer(cmd,0));VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};VK(vkBeginCommandBuffer(cmd,&begin));vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,1,&set,0,NULL);vkCmdDispatch(cmd,1,1,1);
        VkMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT,.dstAccessMask=VK_ACCESS_HOST_READ_BIT};vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&barrier,0,NULL,0,NULL);VK(vkEndCommandBuffer(cmd));VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cmd};VkFenceCreateInfo fi={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};VkFence fence;VK(vkCreateFence(device,&fi,NULL,&fence));VK(vkQueueSubmit(queue,1,&submit,fence));VK(vkWaitForFences(device,1,&fence,VK_TRUE,10000000000ull));
        if(legacy>=2&&variant==0){
            if(legacy==3){
                unsigned worst=0;
                for(unsigned j=0;j<words;j++){
                    for(unsigned half=0;half<2;half++){
                        uint32_t a=(mapped[j]>>(16*half))&65535u,b=(expected[j]>>(16*half))&65535u;
                        unsigned diff=a>b?a-b:b-a;if(!(a&32767u)&&!(b&32767u))diff=0;if(diff>worst)worst=diff;
                    }
                }
                precision_ok=worst<=1;printf("  %s scalar vs CPU: %u half ULP maximum\n",name,worst);
            }
            memcpy(expected,mapped,words*4u);
        }
        else{unsigned mismatches=0;for(unsigned j=0;j<words;j++)if(mapped[j]!=expected[j]){if(mismatches<2)printf("  %s word %u: %#x expected %#x\n",name,j,mapped[j],expected[j]);mismatches++;}
        int pass=(legacy==1?mismatches!=0:mismatches==0)&&precision_ok;checks++;if(!pass)failed++;printf("%s %s: %u/%u mismatches%s\n",pass?"PASS":"FAIL",name,mismatches,words,legacy==1?" (expected legacy failure)":legacy>=2?" (scalar GPU reference)":"");}
        vkDestroyFence(device,fence,NULL);vkDestroyPipeline(device,pipeline,NULL);vkDestroyShaderModule(device,module,NULL);
        }free(expected);
    }
    fclose(manifest);VK(vkDeviceWaitIdle(device));vkDestroyCommandPool(device,cp,NULL);vkDestroyDescriptorPool(device,pool,NULL);vkDestroyPipelineLayout(device,layout,NULL);vkDestroyDescriptorSetLayout(device,dsl,NULL);vkUnmapMemory(device,mem);vkDestroyBuffer(device,buffer,NULL);vkFreeMemory(device,mem,NULL);vkDestroyDevice(device,NULL);vkDestroyInstance(instance,NULL);printf("warp32 proof: %u checks, %u failed\n",checks,failed);return failed?1:0;
}
