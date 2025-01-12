package com.core.data;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@NoArgsConstructor
public class Session {
    private Integer id;
    private SessionState state;
    private List<CoreNode> nodes = new ArrayList<>();
    private List<CoreLink> links = new ArrayList<>();
}
