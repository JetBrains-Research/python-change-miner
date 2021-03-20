#!/usr/bin/env bash

BASEDIR=$(dirname "$0")
cd "$BASEDIR"

sudo apt-get update
sudo apt-get install gcc zlib1g-dev build-essential
sudo apt install libfreetype6 libfreetype6-dev

wget https://github.com/graalvm/graalvm-ce-builds/releases/download/vm-21.0.0.2/graalvm-ce-java11-linux-amd64-21.0.0.2.tar.gz
tar -xvzf graalvm-ce-java11-linux-amd64-21.0.0.2.tar.gz

sudo mkdir /usr/lib/jvm
sudo mv graalvm-ce-java11-21.0.0.2/ /usr/lib/jvm

echo 'export PATH=/usr/lib/jvm/graalvm-ce-java11-21.0.0.2/bin:$PATH' >> ~/.bashrc
echo 'export JAVA_HOME=/usr/lib/jvm/graalvm-ce-java11-21.0.0.2' >> ~/.bashrc

source ~/.bashrc

java -version
gu install native-image


java -agentlib:native-image-agent=config-output-dir="." -cp "build/install/gumtree/lib/*" com.github.gumtreediff.client.Run
java -agentlib:native-image-agent=config-output-dir="." -cp "build/install/gumtree/lib/*" com.github.gumtreediff.client.Ru jsondiff jni-config.json serialization-config.json

native-image --initialize-at-build-time=org.eclipse.jdt.internal.compiler,org.eclipse.core.runtime.Platform,org.eclipse.core.internal.runtime.Messages,org.eclipse.jdt.internal.core.JavaModelManager,org.eclipse.jdt.internal.core,org.eclipse.jdt.internal.core.ExternalFoldersManager,org.eclipse.core.runtime.Path,org.eclipse.osgi.util.NLS,org.eclipse.core.internal.runtime.CommonMessages,org.eclipse.core.internal.utils.Messages,org.eclipse.jdt.internal.core.JavaModelStatus,org.eclipse.core.runtime.Status,org.eclipse.core.internal.preferences.PreferencesService,org.eclipse.core.internal.preferences.InstancePreferences,org.eclipse.core.internal.preferences.ConfigurationPreferences,org.eclipse.core.internal.preferences.BundleDefaultPreferences,org.eclipse.core.internal.preferences.EclipsePreferences,org.eclipse.core.internal.preferences.DefaultPreferences -H:ReflectionConfigurationFiles=reflect-config.json -H:ResourceConfigurationFiles=resource-config.json --initialize-at-run-time=org.eclipse.jdt.internal.core.ClasspathEntry -cp "build/install/gumtree/lib/*" com.github.gumtreediff.client.Run gumtree --no-fallback

cp ../pythonparser /tmp