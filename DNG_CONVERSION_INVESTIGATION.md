# DNG Conversion Failure Investigation - Linux Platform

## Problem Summary

DNG conversion was failing silently on Linux despite:
1. DNGLab binary being found and configured correctly
2. Binary passing the `--help` test
3. Conversion jobs being processed with correct arguments
4. Workers reporting "finished conversion" but no DNG files being created

## Root Cause Analysis

After investigating the pydngconverter codebase, I identified several critical issues:

### 1. Silent Subprocess Failures
**Location**: `pydngconverter/main.py:191-194`

**Issue**: The original `convert_file` method doesn't check subprocess return codes:
```python
proc = await asyncio.create_subprocess_exec(
    self.bin_exec, *dng_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
)
await proc.wait()  # ❌ No return code checking
```

**Impact**: DNGLab failures were completely silent - the process would "complete" even if DNGLab returned error codes.

### 2. Wine Path Conversion on Linux
**Location**: `pydngconverter/compat.py:88-95`

**Issue**: The library assumes all Linux systems use Wine to run Adobe DNG Converter:
```python
if plat.is_nix:
    # dngconverter runs in wine on *nix,
    # but it requires windows-type paths.
    _path = await wine_path(_path)  # ❌ Tries to convert to Windows paths
```

**Impact**: When using native DNGLab on Linux, paths were being incorrectly converted to Wine/Windows format.

### 3. Missing Error Logging
**Issue**: No stderr/stdout capture and logging from the subprocess execution.

**Impact**: DNGLab error messages were never visible, making debugging impossible.

## Solutions Implemented

### 1. Enhanced Error Handling Patch
Applied to `src/eir/processor.py` in the `convert_raw_to_dng` method:

```python
async def patched_convert_file(self, *, destination: str = None, job = None, log=None):
    """Enhanced convert_file with better error handling and logging."""
    # ... setup code ...
    
    try:
        proc = await asyncio.create_subprocess_exec(
            self.bin_exec, 
            *dng_args, 
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        # ✅ Check return code and log any errors
        if proc.returncode != 0:
            log.error("DNGLab conversion failed with return code %d", proc.returncode)
            if stderr:
                stderr_text = stderr.decode('utf-8', errors='replace')
                log.error("DNGLab stderr: %s", stderr_text)
            # ... more error handling ...
        else:
            log.info("DNGLab conversion succeeded (return code 0)")
            
    except Exception as e:
        log.error("Exception during DNGLab subprocess execution: %s", e)
        raise
```

### 2. Linux Native Path Patch
Applied to avoid Wine path conversion when using DNGLab:

```python
async def patched_get_compat_path(path):
    # Use native path on Linux when DNGLab is configured
    native_path = str(Path(path))
    self._logger.debug(f"Patched compat path: {path} -> {native_path}")
    return native_path

pydngconverter.compat.get_compat_path = patched_get_compat_path
```

### 3. Enhanced Command Logging
Added comprehensive logging of:
- Full command being executed
- Binary path validation
- Source file existence checks
- Destination directory validation
- Current working directory
- Detailed stdout/stderr output

## Testing and Validation

Created two test scripts to validate the fixes:

1. **`test_dnglab_debug.py`**: Tests both direct DNGLab execution and pydngconverter integration
2. **`validate_patches.py`**: Validates that patches are applied correctly

## Expected Results

With these patches:

1. **Visible Errors**: Any DNGLab failures will now be logged with detailed error messages
2. **Correct Paths**: Linux systems will use native paths instead of Wine paths
3. **Better Debugging**: Full command execution details are logged
4. **Error Detection**: Return code checking ensures failures are detected

## Platform-Specific Behavior

- **Linux with DNGLab**: Uses native paths and enhanced error handling
- **Linux with Adobe DNG Converter**: Uses Wine paths (unchanged behavior)
- **Windows/macOS**: No changes to existing behavior

## Files Modified

1. `/Users/abk/dev/git/eir/src/eir/processor.py` - Applied Linux-specific patches
2. `/Users/abk/dev/git/eir/test_dnglab_debug.py` - Created debug test script
3. `/Users/abk/dev/git/eir/validate_patches.py` - Created patch validation script

## Next Steps

1. Test the patched code with actual RAW files on Linux
2. Run integration tests to ensure DNG conversion works
3. Monitor logs for any remaining issues
4. Consider contributing the error handling improvements back to pydngconverter project

## Key Insight

The core issue was that pydngconverter was designed primarily for Adobe DNG Converter with Wine on Linux, but when using native DNGLab, it needed Linux-specific adaptations for both path handling and error reporting.