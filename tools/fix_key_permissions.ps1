<#
.SYNOPSIS
    Fixes "UNPROTECTED PRIVATE KEY FILE" / "bad permissions" for an SSH key on Windows.

.DESCRIPTION
    Windows OpenSSH refuses a private key whose ACL grants access to anyone
    besides the owner.

    This edits ONLY the DACL (the permission list) and deliberately does not
    touch the file's owner. That distinction matters: changing an owner needs
    the SeSecurityPrivilege / SeTakeOwnershipPrivilege, which a normal
    non-elevated account does not hold, and attempting it fails with

        The process does not possess the 'SeSecurityPrivilege' privilege

    A file's owner, however, can always rewrite that file's DACL - no elevation
    required. Since the key lives under your own profile you already own it, so
    there is nothing to take ownership of.

    The rules are rebuilt rather than edited, which also clears orphaned entries
    whose account no longer resolves to a name (ssh shows those as
    `MACHINE\ (S-1-5-21-...)` with an empty user, and they cannot be removed
    with `icacls /remove` because there is no name to pass).

.PARAMETER KeyPath
    Path to the PRIVATE key (the file with no .pub extension).
    Defaults to ~\.ssh\nazarick_ci.

.EXAMPLE
    .\tools\fix_key_permissions.ps1
    .\tools\fix_key_permissions.ps1 -KeyPath $env:USERPROFILE\.ssh\id_rsa
#>

[CmdletBinding()]
param(
    [string]$KeyPath = "$env:USERPROFILE\.ssh\nazarick_ci"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $KeyPath)) {
    Write-Error "No such file: $KeyPath"
    exit 1
}

if ($KeyPath -like "*.pub") {
    Write-Warning "$KeyPath looks like a PUBLIC key. Permissions only matter for"
    Write-Warning "the private key - the one with no .pub extension. Nothing to do."
    exit 0
}

$resolved = (Resolve-Path -LiteralPath $KeyPath).Path
$me = "$env:USERDOMAIN\$env:USERNAME"

Write-Host "Fixing permissions on: $resolved" -ForegroundColor Cyan
Write-Host "  granting sole access to: $me"

# Read the existing security descriptor. Get-Acl (rather than a fresh
# FileSecurity object) is important: a new object has no owner, so Set-Acl
# would try to write one and hit the privilege error described above.
$acl = Get-Acl -LiteralPath $resolved

$currentOwner = $acl.Owner
Write-Host "  current owner: $currentOwner"
if ($currentOwner -ine $me) {
    Write-Warning "You are not the owner of this file."
    Write-Warning "The DACL rewrite below will probably fail. If it does, either:"
    Write-Warning "  * re-run this script in an ELEVATED PowerShell (Run as administrator), or"
    Write-Warning "  * delete the key and regenerate it - a key you create is owned by you:"
    Write-Warning "      Remove-Item '$resolved','$resolved.pub'"
    Write-Warning "      ssh-keygen -t ed25519 -f '$resolved' -C `"github-actions`""
}

# $true  = stop inheriting from the parent folder
# $false = do NOT copy the inherited rules in as explicit ones
$acl.SetAccessRuleProtection($true, $false)

# Drop every remaining explicit rule, including any whose SID no longer
# resolves - iterating a copy so the collection can be modified safely.
foreach ($rule in @($acl.Access)) {
    [void]$acl.RemoveAccessRuleSpecific($rule)
}

$acl.AddAccessRule(
    (New-Object System.Security.AccessControl.FileSystemAccessRule(
        $me, "FullControl", "Allow")))

try {
    # Only the access rules were modified, so only the DACL is written -
    # the owner is left exactly as it was.
    Set-Acl -LiteralPath $resolved -AclObject $acl
} catch [System.Security.AccessControl.PrivilegeNotHeldException] {
    Write-Host ""
    Write-Error @"
Could not rewrite the permissions: $($_.Exception.Message)

This normally means you do not own the file. Easiest fix - regenerate the key,
since one you create yourself is owned by you:

    Remove-Item '$resolved','$resolved.pub'
    ssh-keygen -t ed25519 -f '$resolved' -C "github-actions"
    .\tools\fix_key_permissions.ps1

Alternatively, re-run this script from an elevated PowerShell.
"@
    exit 1
}

Write-Host "`nResulting permissions:" -ForegroundColor Cyan
& icacls.exe $resolved

# Verify rather than assume: ssh only accepts the key if exactly one principal
# has access, and that principal is you.
$rules = @((Get-Acl -LiteralPath $resolved).Access)
if ($rules.Count -eq 1 -and $rules[0].IdentityReference.Value -ieq $me) {
    Write-Host "`nOK - exactly one access rule, and it is yours." -ForegroundColor Green
    Write-Host "ssh will now accept this key."
} else {
    Write-Warning "`nExpected one access rule for $me, found $($rules.Count):"
    $rules | ForEach-Object {
        Write-Warning "  $($_.IdentityReference.Value) - $($_.FileSystemRights)"
    }
    Write-Warning "ssh may still refuse the key."
}
