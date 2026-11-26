#!/usr/bin/env bash
# Prints the next release version of a chart.
#   MAJOR.MINOR -> taken from Chart.yaml (bumped by hand for breaking changes / features)
#   PATCH       -> latest released patch for that MAJOR.MINOR + 1 (git tags <name>-chart-vX.Y.Z)
# Usage: chart-next-version.sh chart/generic
set -euo pipefail

chart_dir="${1:?usage: $0 <chart-dir>}"
name=$(yq '.name' "$chart_dir/Chart.yaml")
base=$(yq '.version' "$chart_dir/Chart.yaml")
major_minor="${base%.*}"
prefix="${name}-chart-v${major_minor}."

latest=$(git tag --list "${prefix}*" | sed "s/^${name}-chart-v//" | sort -V | tail -n1)
if [[ -z "$latest" ]]; then
  next="${major_minor}.0"
else
  next="${major_minor}.$(( ${latest##*.} + 1 ))"
fi
echo "$next"
