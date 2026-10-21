/* Lab loader for the T5 cgroup program.
 * GPL-2.0-only because it links libbpf and attaches a GPL bpf program.
 * It refuses every cgroup except one leaf under vantio-t5-lab.slice.
 */
#define _GNU_SOURCE

#include <arpa/inet.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/bpf.h>
#include <netinet/in.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#define CGROUP_PREFIX "/sys/fs/cgroup/vantio-t5-lab.slice/"
#define CGROUP_LEAF "t5-drill"
#define ALLOW_PORT 18080
#define DENY_PORT 9

struct t5_cfg {
	unsigned long long window_ns;
	unsigned int enforce;
	unsigned int max_label;
	unsigned int max_queries;
	unsigned int entropy_min_length;
	unsigned int entropy_userspace;
	unsigned int n_names;
	unsigned int n_resolvers;
	unsigned int n_icmp;
	unsigned int n_ports;
	unsigned int pad;
};

struct name_slot {
	unsigned int len;
	unsigned char bytes[64];
};

struct addr_slot {
	unsigned int addr;
	unsigned int set;
};

struct port_slot {
	unsigned int port;
	unsigned int set;
};

/* VANTIO_PARTNER_MARKERS: comma-separated deployment-partner substrings. Unset means none. */
static int names_partner(const char *path)
{
	const char *raw = getenv("VANTIO_PARTNER_MARKERS");
	char token[128];
	size_t len = 0;

	if (raw == NULL)
		return 0;
	for (;; raw++) {
		if (*raw == ',' || *raw == '\0') {
			while (len > 0 && token[len - 1] == ' ')
				len--;
			token[len] = '\0';
			if (len > 0 && strstr(path, token) != NULL)
				return 1;
			len = 0;
			if (*raw == '\0')
				return 0;
			continue;
		}
		if (len == 0 && *raw == ' ')
			continue;
		if (len < sizeof(token) - 1) {
			char c = *raw;
			token[len++] = (c >= 'A' && c <= 'Z') ? (char)(c - 'A' + 'a') : c;
		}
	}
}

static int cgroup_ok(const char *path)
{
	const char *leaf;
	size_t prefix = sizeof(CGROUP_PREFIX) - 1;

	if (path == NULL || names_partner(path) || strstr(path, "vantio-enrolled") != NULL)
		return 0;
	if (strncmp(path, CGROUP_PREFIX, prefix) != 0)
		return 0;
	leaf = path + prefix;
	if (strcmp(leaf, CGROUP_LEAF) != 0)
		return 0;
	if (strchr(leaf, '/') != NULL)
		return 0;
	return 1;
}

static int mkdir_leaf(const char *path)
{
	if (mkdir("/sys/fs/cgroup/vantio-t5-lab.slice", 0755) != 0 && errno != EEXIST)
		return -1;
	if (mkdir(path, 0755) != 0 && errno != EEXIST)
		return -1;
	return 0;
}

static int listen_port(unsigned short port)
{
	int fd;
	int one = 1;
	struct sockaddr_in addr;

	fd = socket(AF_INET, SOCK_STREAM, 0);
	if (fd < 0)
		return -1;
	setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
	memset(&addr, 0, sizeof(addr));
	addr.sin_family = AF_INET;
	addr.sin_port = htons(port);
	addr.sin_addr.s_addr = htonl(0x7f000001);
	if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0 || listen(fd, 4) != 0) {
		close(fd);
		return -1;
	}
	return fd;
}

static int connect_result(unsigned short port)
{
	int fd;
	int flags;
	int rc;
	struct sockaddr_in addr;

	fd = socket(AF_INET, SOCK_STREAM, 0);
	if (fd < 0)
		return -errno;
	flags = fcntl(fd, F_GETFL, 0);
	fcntl(fd, F_SETFL, flags | O_NONBLOCK);
	memset(&addr, 0, sizeof(addr));
	addr.sin_family = AF_INET;
	addr.sin_port = htons(port);
	addr.sin_addr.s_addr = htonl(0x7f000001);
	rc = connect(fd, (struct sockaddr *)&addr, sizeof(addr));
	if (rc != 0 && errno == EINPROGRESS) {
		struct pollfd pollfd;
		int err = 0;
		socklen_t len = sizeof(err);

		pollfd.fd = fd;
		pollfd.events = POLLOUT;
		if (poll(&pollfd, 1, 800) <= 0)
			err = ETIMEDOUT;
		else if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &err, &len) != 0)
			err = errno;
		close(fd);
		return err == 0 ? 0 : -err;
	}
	if (rc == 0) {
		close(fd);
		return 0;
	}
	rc = -errno;
	close(fd);
	return rc;
}

static int join_cgroup(const char *path)
{
	char procs[256];
	int fd;
	char pid[32];
	int len;

	if (snprintf(procs, sizeof(procs), "%s/cgroup.procs", path) >= (int)sizeof(procs))
		return -1;
	fd = open(procs, O_WRONLY);
	if (fd < 0)
		return -1;
	len = snprintf(pid, sizeof(pid), "%d", getpid());
	if (write(fd, pid, (size_t)len) != len) {
		close(fd);
		return -1;
	}
	close(fd);
	return 0;
}

static int update_map(struct bpf_object *obj, const char *name, const void *key, const void *value)
{
	struct bpf_map *map = bpf_object__find_map_by_name(obj, name);
	int fd;

	if (map == NULL)
		return -1;
	fd = bpf_map__fd(map);
	if (fd < 0)
		return -1;
	return bpf_map_update_elem(fd, key, value, BPF_ANY);
}

static int install_policy(struct bpf_object *obj)
{
	struct t5_cfg cfg;
	struct name_slot name;
	struct addr_slot resolver;
	struct port_slot port;
	unsigned int zero = 0;
	const char *listed = "allowed.example";

	memset(&cfg, 0, sizeof(cfg));
	cfg.window_ns = 10000000000ULL;
	cfg.enforce = 1;
	cfg.max_label = 32;
	cfg.max_queries = 30;
	cfg.entropy_min_length = 12;
	cfg.entropy_userspace = 1;
	cfg.n_names = 1;
	cfg.n_resolvers = 1;
	cfg.n_icmp = 0;
	cfg.n_ports = 1;
	memset(&name, 0, sizeof(name));
	name.len = (unsigned int)strlen(listed);
	memcpy(name.bytes, listed, name.len);
	memset(&resolver, 0, sizeof(resolver));
	resolver.addr = 0x7f000001;
	resolver.set = 1;
	memset(&port, 0, sizeof(port));
	port.port = ALLOW_PORT;
	port.set = 1;
	if (update_map(obj, "t5_cfg_map", &zero, &cfg) != 0)
		return -1;
	if (update_map(obj, "t5_name_map", &zero, &name) != 0)
		return -1;
	if (update_map(obj, "t5_resolver_map", &zero, &resolver) != 0)
		return -1;
	if (update_map(obj, "t5_port_map", &zero, &port) != 0)
		return -1;
	return 0;
}

static int attach_program(struct bpf_object *obj, int cgroup_fd, const char *section, enum bpf_attach_type type)
{
	struct bpf_program *prog;

	bpf_object__for_each_program(prog, obj) {
		const char *name = bpf_program__section_name(prog);

		if (name != NULL && strcmp(name, section) == 0)
			return bpf_prog_attach(bpf_program__fd(prog), cgroup_fd, type, 0);
	}
	return -1;
}

static void detach_all(int cgroup_fd)
{
	bpf_prog_detach(cgroup_fd, BPF_CGROUP_INET_EGRESS);
	bpf_prog_detach(cgroup_fd, BPF_CGROUP_INET4_CONNECT);
	bpf_prog_detach(cgroup_fd, BPF_CGROUP_INET6_CONNECT);
}

static void read_boot(char *buf, size_t len)
{
	FILE *file = fopen("/proc/sys/kernel/random/boot_id", "r");
	size_t n;

	if (file == NULL) {
		snprintf(buf, len, "unread");
		return;
	}
	n = fread(buf, 1, len - 1, file);
	fclose(file);
	buf[n] = 0;
	if (n > 0 && buf[n - 1] == '\n')
		buf[n - 1] = 0;
}

static int child_checks(const char *cgroup, int *allow_rc, int *deny_rc)
{
	if (join_cgroup(cgroup) != 0)
		return -1;
	*allow_rc = connect_result(ALLOW_PORT);
	*deny_rc = connect_result(DENY_PORT);
	return 0;
}

int main(int argc, char **argv)
{
	struct bpf_object *obj = NULL;
	int cgroup_fd = -1;
	int allow_listen = -1;
	int deny_listen = -1;
	int outside;
	int allow_rc = -1;
	int deny_rc = -1;
	int loaded = 0;
	int attached = 0;
	int user_port_pass = 0;
	int outside_ok = 0;
	char boot[80];
	pid_t child;
	int status = 0;
	const char *object;
	const char *cgroup;

	if (argc == 3 && strcmp(argv[1], "path-check") == 0)
		return cgroup_ok(argv[2]) ? 0 : 4;
	if (argc != 3) {
		fprintf(stderr, "usage: t5_load OBJECT CGROUP\n");
		return 2;
	}
	object = argv[1];
	cgroup = argv[2];
	read_boot(boot, sizeof(boot));
	if (!cgroup_ok(cgroup) || mkdir_leaf(cgroup) != 0) {
		printf("{\"verifier\":\"not_run\",\"attached\":false,\"user_port\":\"not_run\",\"boot_id\":\"%s\",\"label\":\"Roadmap\"}\n", boot);
		return 4;
	}
	libbpf_set_strict_mode(LIBBPF_STRICT_ALL);
	obj = bpf_object__open_file(object, NULL);
	if (obj == NULL || bpf_object__load(obj) != 0) {
		printf("{\"verifier\":\"rejected\",\"attached\":false,\"user_port\":\"not_run\",\"boot_id\":\"%s\",\"label\":\"Roadmap\"}\n", boot);
		return 2;
	}
	loaded = 1;
	if (install_policy(obj) != 0)
		goto out;
	cgroup_fd = open(cgroup, O_DIRECTORY);
	allow_listen = listen_port(ALLOW_PORT);
	deny_listen = listen_port(DENY_PORT);
	if (cgroup_fd < 0 || allow_listen < 0 || deny_listen < 0)
		goto out;
	if (attach_program(obj, cgroup_fd, "cgroup_skb/egress", BPF_CGROUP_INET_EGRESS) != 0)
		goto out;
	if (attach_program(obj, cgroup_fd, "cgroup/connect4", BPF_CGROUP_INET4_CONNECT) != 0)
		goto out;
	if (attach_program(obj, cgroup_fd, "cgroup/connect6", BPF_CGROUP_INET6_CONNECT) != 0)
		goto out;
	attached = 1;
	outside = connect_result(DENY_PORT);
	outside_ok = outside == 0;
	child = fork();
	if (child == 0) {
		int joined;

		close(allow_listen);
		close(deny_listen);
		joined = child_checks(cgroup, &allow_rc, &deny_rc);
		if (joined != 0)
			_exit(3);
		if (allow_rc == 0 && (deny_rc == -EPERM || deny_rc == -EACCES))
			_exit(0);
		_exit(5);
	}
	if (child > 0) {
		waitpid(child, &status, 0);
		user_port_pass = WIFEXITED(status) && WEXITSTATUS(status) == 0 && outside_ok;
	}
out:
	if (cgroup_fd >= 0 && attached)
		detach_all(cgroup_fd);
	if (allow_listen >= 0)
		close(allow_listen);
	if (deny_listen >= 0)
		close(deny_listen);
	if (cgroup_fd >= 0)
		close(cgroup_fd);
	rmdir(cgroup);
	rmdir("/sys/fs/cgroup/vantio-t5-lab.slice");
	if (obj != NULL)
		bpf_object__close(obj);
	printf(
		"{\"verifier\":\"%s\",\"attached\":%s,\"user_port\":\"%s\",\"outside_unaffected\":%s,\"cgroup\":\"%s\",\"enrolled_slice\":false,\"boot_id\":\"%s\",\"label\":\"%s\"}\n",
		loaded ? "accepted" : "rejected",
		attached ? "true" : "false",
		user_port_pass ? "pass" : "fail",
		outside_ok ? "true" : "false",
		cgroup_ok(cgroup) ? cgroup : "",
		boot,
		user_port_pass ? "Lab-only" : "Roadmap");
	return user_port_pass ? 0 : (loaded ? 3 : 2);
}
