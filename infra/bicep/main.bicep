targetScope = 'subscription'

@description('Short lowercase project prefix')
param projectName string = 'vichome'
param environment string = 'dev'
param location string = 'australiaeast'
param sqlAdministratorObjectId string

var suffix = uniqueString(subscription().id, projectName, environment)
var resourceGroupName = 'rg-${projectName}-${environment}'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: {
    project: projectName
    environment: environment
    workload: 'data-platform'
  }
}

module platform 'modules/platform.bicep' = {
  name: 'platform'
  scope: rg
  params: {
    projectName: projectName
    environment: environment
    location: location
    suffix: suffix
    sqlAdministratorObjectId: sqlAdministratorObjectId
  }
}

output resourceGroupName string = rg.name
output functionAppName string = platform.outputs.functionAppName
output storageAccountName string = platform.outputs.storageAccountName
output sqlServerName string = platform.outputs.sqlServerName
output sqlDatabaseName string = platform.outputs.sqlDatabaseName
output keyVaultName string = platform.outputs.keyVaultName
