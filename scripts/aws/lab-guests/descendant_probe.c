#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>

/* vfork child. The caller is already in the enrolled cgroup.
 * The child shares that cgroup, drops to uid 65534, opens the path, and
 * sends one UDP datagram to 192.0.2.2:9. It must not return from the child.
 */
int main(int argc, char **argv) {
    if (argc < 2) {
        return 2;
    }
    const char *path = argv[1];
    pid_t child = vfork();
    if (child < 0) {
        fprintf(stderr, "vfork %d\n", errno);
        return 4;
    }
    if (child == 0) {
        int file_errno = 0;
        int net_errno = 0;
        if (setresuid(65534, 65534, 0) != 0) {
            dprintf(STDOUT_FILENO, "setuid %d pid %d\n", errno, (int)getpid());
            _exit(0);
        }
        int fd = open(path, O_RDONLY);
        if (fd < 0) {
            file_errno = errno;
        } else {
            char buf[1];
            if (read(fd, buf, 1) < 0) {
                file_errno = errno;
            }
            close(fd);
        }
        int sock = socket(AF_INET, SOCK_DGRAM, 0);
        if (sock < 0) {
            net_errno = errno;
        } else {
            struct sockaddr_in dst;
            memset(&dst, 0, sizeof(dst));
            dst.sin_family = AF_INET;
            dst.sin_port = htons(9);
            inet_pton(AF_INET, "192.0.2.2", &dst.sin_addr);
            char msg = 'x';
            if (sendto(sock, &msg, 1, 0, (struct sockaddr *)&dst, sizeof(dst)) < 0) {
                net_errno = errno;
            }
            close(sock);
        }
        dprintf(STDOUT_FILENO, "file %d net %d pid %d\n", file_errno, net_errno, (int)getpid());
        _exit(0);
    }
    int status = 0;
    waitpid(child, &status, 0);
    return 0;
}
