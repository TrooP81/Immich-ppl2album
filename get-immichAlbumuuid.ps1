<#
.SYNOPSIS
    Finds the UUID of an Immich album by its name.
.DESCRIPTION
    This script connects to an Immich instance, retrieves all albums,
    and searches for an album with a specific name to output its UUID.
.PARAMETER ImmichBaseUrl
    The base URL of your Immich instance (e.g., "http://localhost:2283").
.PARAMETER ApiKey
    Your Immich API key.
.PARAMETER TargetAlbumName
    The name of the album for which you want to find the UUID.
.EXAMPLE
    .\Get-ImmichAlbumUuid.ps1 -ImmichBaseUrl "http://immich.example.com" -ApiKey "YOUR_API_KEY" -TargetAlbumName "Vacation Photos"
    This will search for an album named "Vacation Photos" on the specified Immich instance.
#>
param (
    [Parameter(Mandatory=$true)]
    [string]$ImmichBaseUrl = "http://localhost:2283",

    [Parameter(Mandatory=$true)]
    [string]$ApiKey,

    [Parameter(Mandatory=$true)]
    [string]$TargetAlbumName
)

# Construct the API URL for fetching all albums
$apiUrl = "$($ImmichBaseUrl.TrimEnd('/'))/api/albums"

# Define headers for the API request
$headers = @{
    "Accept"      = "application/json"
    "x-api-key"   = $ApiKey
}

Write-Host "Attempting to connect to Immich instance at $ImmichBaseUrl to find album '$TargetAlbumName'..."

try {
    # Make the API request
    Write-Host "Fetching all albums from $apiUrl..."
    $response = Invoke-RestMethod -Uri $apiUrl -Method Get -Headers $headers -ContentType "application/json"

    if ($null -eq $response) {
        Write-Error "Received an empty response from the server. Please check the Immich URL and network connectivity."
        exit 1
    }

    # Find the album by name
    $foundAlbum = $response | Where-Object { $_.albumName -eq $TargetAlbumName }

    if ($null -ne $foundAlbum) {
        # If multiple albums have the same name, Invoke-RestMethod might return a collection.
        # We'll take the first one found. If album names are unique, this will be the only one.
        $albumId = if ($foundAlbum -is [array]) { $foundAlbum[0].id } else { $foundAlbum.id }
        
        if ($albumId) {
            Write-Host ""
            Write-Host "----------------------------------------"
            Write-Host "Album Found!"
            Write-Host "Name: $($TargetAlbumName)"
            Write-Host "UUID: $($albumId)"
            Write-Host "----------------------------------------"
        } else {
            Write-Warning "Album '$TargetAlbumName' was found, but it does not have an 'id' property."
        }
    } else {
        Write-Warning "Album with name '$TargetAlbumName' not found."
        Write-Host "Available albums:"
        $response | ForEach-Object { Write-Host "- $($_.albumName) (ID: $($_.id))" }
    }
}
catch {
    Write-Error "An error occurred while trying to fetch albums or find the target album:"
    Write-Error $_.Exception.Message
    if ($_.Exception.Response) {
        Write-Error "Status Code: $($_.Exception.Response.StatusCode)"
        Write-Error "Status Description: $($_.Exception.Response.StatusDescription)"
        try {
            $errorResponse = $_.Exception.Response.GetResponseStream()
            $streamReader = New-Object System.IO.StreamReader($errorResponse)
            $errorBody = $streamReader.ReadToEnd()
            $streamReader.Close()
            $errorResponse.Close()
            Write-Error "Response Body: $errorBody"
        } catch {
            Write-Warning "Could not read error response body."
        }
    }
    exit 1
}

