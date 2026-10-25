PY := /usr/bin/python3
# For `diff <(…)`. CLT ships GNU make 3.81, which ignores .SHELLFLAGS: chain dependent commands with &&.
SHELL := /bin/bash

APP := build/AgentUsageMonitor.app
APPEX := $(APP)/Contents/PlugIns/AgentUsageMonitorWidget.appex
ICONSET := build/AppIcon.iconset
AGENT := build/com.windroc.agent-usage-monitor.plist
# $${HOME:?}: an unset HOME fails instead of resolving to /Applications.
DEST = $${HOME:?}/Applications/AgentUsageMonitor.app
LINK = $${HOME:?}/.local/bin/agent-usage-monitor
LOG = $${HOME:?}/Library/Logs/agent-usage-monitor.log
PLIST = $${HOME:?}/Library/LaunchAgents/com.windroc.agent-usage-monitor.plist
LSREGISTER := /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

test:
	$(PY) -m unittest discover -s tests -t .

# NFR-4: no personal data in tracked files; rules in tests/pii_scan.py, allowlist in tests/pii-allowlist.txt.
pii-scan:
	$(PY) tests/pii_scan.py

# Repo-local git config only: enables .githooks/pre-push, the same scan before every push.
hooks:
	git config core.hooksPath .githooks

swift-test:
	mkdir -p build
	xcrun swiftc macos/Widget/Snapshot.swift macos/Host/Alerts.swift macos/Host/Settings.swift macos/Tests/main.swift \
		-o build/swift-test
	build/swift-test

app:
	rm -rf $(APP) $(ICONSET)
	mkdir -p $(APP)/Contents/MacOS $(APP)/Contents/Resources $(APPEX)/Contents/MacOS $(ICONSET)
	cp macos/Host/Info.plist $(APP)/Contents/Info.plist
	# One 1024 px image; macOS scales it down and, on macOS 26, fits it to the system icon shape.
	cp macos/Host/AppIcon.png $(ICONSET)/icon_512x512@2x.png
	iconutil -c icns $(ICONSET) -o $(APP)/Contents/Resources/AppIcon.icns
	cp macos/Widget/Info.plist $(APPEX)/Contents/Info.plist
	# A new build version each build, so macOS sees an install as a new build of the app and widget.
	V=$$(date +%s) && plutil -replace CFBundleVersion -string "$$V" $(APP)/Contents/Info.plist && \
		plutil -replace CFBundleVersion -string "$$V" $(APPEX)/Contents/Info.plist
	xcrun swiftc -O macos/Host/Alerts.swift macos/Host/Settings.swift macos/Host/SettingsView.swift macos/Host/main.swift \
		-o $(APP)/Contents/MacOS/AgentUsageMonitor
	xcrun swiftc -O -parse-as-library -application-extension macos/Widget/Snapshot.swift macos/Widget/AgentUsageMonitorWidget.swift \
		-Xlinker -e -Xlinker _NSExtensionMain -o $(APPEX)/Contents/MacOS/AgentUsageMonitorWidget
	codesign --force -s - --entitlements macos/Widget/widget.entitlements $(APPEX)
	codesign --force -s - $(APP)
	sed "s|@HOME@|$${HOME:?}|g" macos/com.windroc.agent-usage-monitor.plist > $(AGENT)

install: app
	if [ -e "$(LINK)" -o -L "$(LINK)" ] && [ "$$(readlink "$(LINK)")" != "$(CURDIR)/bin/agent-usage-monitor" ]; then \
		echo "agent-usage-monitor: $(LINK) exists and is not a link to $(CURDIR)/bin/agent-usage-monitor" >&2; exit 1; fi
	rm -rf "$(DEST)"
	ditto $(APP) "$(DEST)"
	$(LSREGISTER) -f "$(DEST)"
	pluginkit -a "$(DEST)/Contents/PlugIns/AgentUsageMonitorWidget.appex"
	# Only our own extension, by its installed path; why: README, Install.
	pkill -f "$(DEST)/Contents/PlugIns/AgentUsageMonitorWidget.appex/Contents/MacOS/AgentUsageMonitorWidget" || true
	mkdir -p "$$(dirname "$(LINK)")"
	ln -sfn "$(CURDIR)/bin/agent-usage-monitor" "$(LINK)"
	mkdir -p "$$(dirname "$(LOG)")"
	umask 077 && touch "$(LOG)" && chmod 600 "$(LOG)"
	mkdir -p "$$(dirname "$(PLIST)")"
	cp $(AGENT) "$(PLIST)"

uninstall:
	-launchctl bootout gui/$$(id -u)/com.windroc.agent-usage-monitor
	-pluginkit -r "$(DEST)/Contents/PlugIns/AgentUsageMonitorWidget.appex"
	-$(LSREGISTER) -u "$(DEST)"
	rm -rf "$(DEST)"
	if [ "$$(readlink "$(LINK)")" = "$(CURDIR)/bin/agent-usage-monitor" ]; then rm "$(LINK)"; fi
	rm -f "$(PLIST)"

# NFR-1: the Python and Swift code holds none of these strings.
check: hooks pii-scan test swift-test app
	! grep -rnF --include='*.py' --include=agent-usage-monitor --include='*.swift' \
		-e 'credentials.json' -e 'auth.json' -e 'security ' -e 'keyring' -e 'oauth' \
		-e 'refresh_token' -e 'anthropic.com' -e 'chatgpt.com' -e 'urllib' -e 'http.client' \
		-e 'socket' -e 'URLSession' -e 'curl' -e '/usr/bin/security' -e 'SecItem' -e 'kSecClass' \
		agent_usage_monitor tests bin/agent-usage-monitor macos
	plutil -lint macos/Host/Info.plist macos/Widget/Info.plist macos/Widget/widget.entitlements \
		macos/com.windroc.agent-usage-monitor.plist $(AGENT)
	codesign --verify --deep --strict $(APP)
	test -s $(APP)/Contents/Resources/AppIcon.icns
	test "$$(plutil -extract CFBundleIconFile raw $(APP)/Contents/Info.plist)" = AppIcon
	diff <(codesign -d --entitlements - --xml $(APPEX) 2>/dev/null | plutil -convert json -o - -) \
		<(plutil -convert json -o - macos/Widget/widget.entitlements)
	@echo "check ok"

clean:
	rm -rf build

.PHONY: test pii-scan hooks swift-test app install uninstall check clean
