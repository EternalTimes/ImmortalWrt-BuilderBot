#!/bin/bash
set -e

# ========== 配置区 ==========
PACKAGES_TO_BUILD="${CUSTOM_PACKAGES}"
PROFILES="${DEVICE_PROFILES}"
RELEASE_TAG_SUFFIX="${RELEASE_TAG_SUFFIX}"
CURRENT_DATE=$(date +%Y%m%d)
SANITIZED_PROFILES=$(echo "$PROFILES" | tr ' ' '_')
EXTRA_SUFFIX="-${SANITIZED_PROFILES}-${CURRENT_DATE}"
if [ -n "$RELEASE_TAG_SUFFIX" ]; then
  EXTRA_SUFFIX="${EXTRA_SUFFIX}-${RELEASE_TAG_SUFFIX}"
fi
EXTRA_IMAGE_NAME_SUFFIX_ARG="EXTRA_IMAGE_NAME_SUFFIX=${EXTRA_SUFFIX}"

# 最大重试次数
max_retry=10
try_count=1

# ========== 主循环 ==========
while [ $try_count -le $max_retry ]; do
  [ -z "$PACKAGES_TO_BUILD" ] && PACKAGES_ARG="" || PACKAGES_ARG="PACKAGES=\"$PACKAGES_TO_BUILD\""
  PROFILES_ARG="PROFILE=\"$PROFILES\""
  BUILD_CMD="make image -j$(nproc) $PROFILES_ARG $PACKAGES_ARG $EXTRA_IMAGE_NAME_SUFFIX_ARG V=s"
  
  echo ">>> [Try $try_count/$max_retry] Build command: $BUILD_CMD"
  # 保存日志
  if eval $BUILD_CMD 2>&1 | tee build.log; then
    echo ">>> Firmware build succeeded!"
    exit 0
  fi

  # 解析无效包
  INVALID_PKGS=$(grep -oP '^\s+\K[^ ]+(?= \(no such package\))' build.log | sort | uniq)
  if [ -z "$INVALID_PKGS" ]; then
    echo ">>> No invalid packages found, build failed for other reasons. Exiting."
    exit 2
  fi

  echo ">>> Invalid packages detected: $INVALID_PKGS"
  # 剔除无效包
  for pkg in $INVALID_PKGS; do
    PACKAGES_TO_BUILD=" $PACKAGES_TO_BUILD "
    PACKAGES_TO_BUILD="${PACKAGES_TO_BUILD// $pkg / }"
    PACKAGES_TO_BUILD=$(echo "$PACKAGES_TO_BUILD" | xargs)
  done

  if [ -z "$PACKAGES_TO_BUILD" ]; then
    echo ">>> All packages filtered out, nothing to build. Exiting."
    exit 3
  fi

  echo ">>> Filtered package list: $PACKAGES_TO_BUILD"
  try_count=$((try_count+1))
done

echo ">>> Exceeded maximum retries ($max_retry), abort."
exit 4
