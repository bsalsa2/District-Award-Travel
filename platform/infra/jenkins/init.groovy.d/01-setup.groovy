import jenkins.model.*
import hudson.plugins.git.*
import org.jenkinsci.plugins.workflow.cps.*

// Configure system settings
def instance = Jenkins.getInstance()
instance.setSystemMessage("District Award Travel - GPU-Accelerated CI/CD Pipeline")
instance.setNumExecutors(2)

// Configure Git
def gitConfig = new GitSCM.DescriptorImpl()
gitConfig.setGlobalConfigName("District Award Travel")
gitConfig.setGlobalConfigEmail("devops@districtaward.travel")

// Configure Docker
def dockerConfig = new com.cloudbees.plugins.credentials.domains.DomainSpecification()
def dockerCredentials = new com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl(
    com.cloudbees.plugins.credentials.common.IdCredentials.lookupStrategy,
    "docker-hub-creds",
    "Docker Hub Credentials",
    "district-award",
    System.getenv("DOCKER_HUB_TOKEN") ?: "default-token"
)

// Save changes
instance.save()
